"""scheduler.py
Heartbeat worker that runs tracker -> simulator -> executor at intervals.

Features:
- Saves tracker snapshots and simulation results to MongoDB.
- Determines viability from simulation before executing trades.
- Sends a "skipped" alert if simulation is not viable.
- Triggers success/failure alerts automatically via executor after execution.
- Uses APScheduler if available; otherwise falls back to a simple sleep loop.
"""
import time
import os
from datetime import datetime, timezone
from typing import Optional, Callable

from .logger import get_logger
from .tracker import (
    load_config,
    fetch_balances,
    fetch_prices,
    propose_rebalance_trades,
    resolve_wallet_address,
)
from .simulator import simulate_trades
from .executor import Executor
from .alerts import send_alerts

# Ensure .env variables are loaded before accessing os.getenv
from dotenv import load_dotenv
load_dotenv()

try:
    from pymongo import MongoClient  # type: ignore
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore

try:
    from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore
except Exception:  # pragma: no cover
    BlockingScheduler = None  # type: ignore


logger = get_logger()

_mongo_client = None
_mongo_db = None


def _get_db():
    global _mongo_client, _mongo_db
    if _mongo_db is not None:
        return _mongo_db
    if MongoClient is None:
        logger.warning("pymongo not installed; snapshots/simulations won't be saved to MongoDB.")
        return None
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "loki_agents")
    try:
        _mongo_client = MongoClient(uri)
        _mongo_db = _mongo_client[db_name]
        return _mongo_db
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to connect MongoDB: {e}")
        _mongo_client = None
        _mongo_db = None
        return None


def _save_snapshot(db, wallet: str, balances: dict, prices: dict, total_value: float) -> None:
    if db is None:
        return
    try:
        db["portfolio_snapshots"].insert_one(
            {
                "timestamp": datetime.now(timezone.utc),
                "wallet": wallet,
                "balances": balances,
                "prices": prices,
                "total_value": float(total_value),
            }
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to insert portfolio snapshot: {e}")


def _save_simulation(db, sim_doc: dict) -> None:
    if db is None:
        return
    try:
        db["rebalance_simulations"].insert_one(sim_doc)
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to insert simulation doc: {e}")


def run_once(
    dry_run: bool = True,
    session_provider: Optional[Callable[[], Optional[str]]] = None,
) -> None:
    cfg = load_config()
    tokens = list(cfg.get("targets", {}).keys())
    prices = fetch_prices(tokens, cfg.get("base_currency", "USD"))
    wallet_address = resolve_wallet_address(cfg, session_provider=session_provider)
    balances = fetch_balances(wallet_address, tokens)
    total_value = sum(balances.get(t, 0.0) * prices.get(t, 0.0) for t in set(balances) | set(prices))

    db = _get_db()
    _save_snapshot(db, wallet_address, balances, prices, total_value)

    threshold_pct = cfg.get("thresholds", {}).get("rebalance_threshold_pct", 2.5)
    min_trade_usd = cfg.get("thresholds", {}).get("min_trade_usd", 100.0)

    trades = propose_rebalance_trades(
        cfg.get("targets", {}), balances, prices, threshold_pct, min_trade_usd
    )

    sim = simulate_trades(
        trades,
        prices,
        slippage_bps=cfg.get("thresholds", {}).get("slippage_tolerance_bps", 50),
        gas_cost_usd=cfg.get("simulation", {}).get("default_gas_cost_usd", 5.0),
        dex=cfg.get("dex", "uniswap_v2"),
    )
    logger.info(f"Simulation summary: {sim.get('summary')}")

    # Save simulation document
    sim_doc = {
        "timestamp": datetime.now(timezone.utc),
        "wallet": wallet_address,
        "tokens": tokens,
        "trades": trades,
        "summary": sim.get("summary", {}),
        "status": "skipped" if not trades else "proposed",
        "viable": bool(trades),
        "reason": None if trades else "no trades proposed (below thresholds or no deviation)",
    }
    _save_simulation(db, sim_doc)

    # Decide viability
    if not trades:
        short = (
            f"{wallet_address[:6]}...{wallet_address[-3:]}"
            if isinstance(wallet_address, str) and len(wallet_address) > 10
            else str(wallet_address)
        )
        message = f"⚠️ Rebalance skipped | Wallet: {short} | Deviation below threshold"
        try:
            send_alerts(wallet_address, "simulation", "skipped", message)
        except Exception as e:  # pragma: no cover
            logger.error(f"Failed to send skipped alert: {e}")
        logger.info("Skipping execution because simulation is not viable.")
        return

    # Execute when viable; executor will send alerts for success/failure/skipped (runtime reasons)
    execu = Executor(cfg, session_provider=session_provider)
    results = execu.execute(trades, dry_run=dry_run)
    logger.info(f"Execution results: {results}")


def main(interval_minutes: int = 5, dry_run: bool = True) -> None:
    interval_seconds = max(60, int(interval_minutes * 60))
    if BlockingScheduler is not None:
        logger.info(f"Starting APScheduler loop; interval={interval_minutes}m dry_run={dry_run}")
        sched = BlockingScheduler()
        sched.add_job(lambda: run_once(dry_run=dry_run), "interval", seconds=interval_seconds, max_instances=1)
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
    else:
        logger.info(
            f"Starting fallback sleep loop; interval={interval_minutes}m dry_run={dry_run} (install APScheduler for better reliability)"
        )
        try:
            while True:
                start = time.time()
                run_once(dry_run=dry_run)
                elapsed = time.time() - start
                sleep_for = max(0, interval_seconds - int(elapsed))
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
