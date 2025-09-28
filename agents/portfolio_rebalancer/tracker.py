"""tracker.py
Fetch balances and prices, compare with targets, and propose rebalancing trades.
This module contains minimal placeholders that are safe to import. Fill in on-chain balance/price fetching later.
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import json
import os

# Ensure .env variables are loaded before accessing os.getenv
from dotenv import load_dotenv
load_dotenv()


def load_config(config_path: Optional[str] = None) -> dict:
    """Load JSON config from `config.json` by default."""
    p = Path(config_path) if config_path else Path(__file__).with_name("config.json")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_wallet_address(
    config: dict,
    session_provider: Optional[Callable[[], Optional[str]]] = None,
) -> str:
    """
    Resolve a wallet address dynamically.

    Priority:
    1) If a session_provider is passed and returns a non-empty string, use it (production/user session).
    2) Environment variables USER_WALLET_ADDRESS or WALLET_ADDRESS if set.
    3) Fallback to config["wallet_address"] (development via config.json).
    Returns an empty string if none are available.
    """
    if session_provider:
        try:
            addr = session_provider()
            if addr:
                return str(addr)
        except Exception:
            # Ignore session provider errors and continue to other sources
            pass

    env_addr = os.getenv("USER_WALLET_ADDRESS") or os.getenv("WALLET_ADDRESS")
    if env_addr:
        return env_addr

    return str(config.get("wallet_address", "") or "")


def fetch_balances(address: str, tokens: List[str]) -> Dict[str, float]:
    """
    Placeholder for on-chain balance fetching.
    Returns a mapping token -> amount.
    """
    return {t: 0.0 for t in tokens}


def fetch_prices(tokens: List[str], base_currency: str = "USD") -> Dict[str, float]:
    """
    Placeholder for token price fetching in `base_currency`.
    Returns a mapping token -> price.
    """
    return {t: 0.0 for t in tokens}


def compute_portfolio_value(balances: Dict[str, float], prices: Dict[str, float]) -> float:
    """Compute total portfolio value using balances and prices."""
    tokens = set(balances) | set(prices)
    return sum(balances.get(t, 0.0) * prices.get(t, 0.0) for t in tokens)


def current_allocations(
    balances: Dict[str, float],
    prices: Dict[str, float],
    tokens: List[str],
) -> Dict[str, float]:
    """Compute current allocation (0..1) per token for the provided token list."""
    total = compute_portfolio_value(balances, prices)
    if total <= 0:
        return {t: 0.0 for t in tokens}
    return {t: (balances.get(t, 0.0) * prices.get(t, 0.0)) / total for t in tokens}


def propose_rebalance_trades(
    targets: Dict[str, float],
    balances: Dict[str, float],
    prices: Dict[str, float],
    threshold_pct: float,
    min_trade_usd: float,
) -> List[Dict[str, Any]]:
    """
    Produce a naive list of buy/sell trades to move from current allocation towards target allocation.
    Returns trades with: token, side ('buy'|'sell'), amount (tokens), value_usd, target_allocation, current_allocation.
    """
    tokens = list(targets.keys())
    curr_alloc = current_allocations(balances, prices, tokens)
    total_value = compute_portfolio_value(balances, prices)
    trades: List[Dict[str, Any]] = []

    for t in tokens:
        target = float(targets.get(t, 0.0))
        current = float(curr_alloc.get(t, 0.0))
        delta = target - current  # positive => need to buy, negative => need to sell
        if total_value <= 0:
            continue
        desired_value_change = delta * total_value
        # Apply thresholds
        if abs(desired_value_change) < max(min_trade_usd, (threshold_pct / 100.0) * total_value):
            continue
        price = prices.get(t, 0.0)
        if price <= 0:
            continue
        amount = abs(desired_value_change) / price
        side = "buy" if delta > 0 else "sell"
        trades.append(
            {
                "token": t,
                "side": side,
                "amount": float(amount),
                "value_usd": float(abs(desired_value_change)),
                "target_allocation": target,
                "current_allocation": current,
            }
        )
    return trades


if __name__ == "__main__":
    # Smoke test of structure
    cfg = load_config()
    tokens = list(cfg.get("targets", {}).keys())
    prices = fetch_prices(tokens, cfg.get("base_currency", "USD"))
    wallet_address = resolve_wallet_address(cfg)
    balances = fetch_balances(wallet_address, tokens)
    proposals = propose_rebalance_trades(
        cfg.get("targets", {}),
        balances,
        prices,
        cfg.get("thresholds", {}).get("rebalance_threshold_pct", 2.5),
        cfg.get("thresholds", {}).get("min_trade_usd", 100.0),
    )
    print("Proposed trades:", proposals)
