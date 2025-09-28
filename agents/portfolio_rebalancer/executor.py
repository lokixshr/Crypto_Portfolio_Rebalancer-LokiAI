"""executor.py
Execute rebalancing trades on a DEX and trigger alerts.
"""
from typing import List, Dict, Any, Optional, Callable
import os
from datetime import datetime, timezone
from .logger import get_logger
from .tracker import resolve_wallet_address
from .alerts import send_alerts
from dotenv import load_dotenv
load_dotenv()


try:  # Optional: MongoDB for executed_trades logging
    from pymongo import MongoClient  # type: ignore
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore


class Executor:
    def __init__(
        self,
        config: Dict[str, Any],
        session_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.config = config
        self.logger = get_logger()
        self.network = config.get("network")
        self.dex = config.get("dex")
        self.wallet_address = resolve_wallet_address(config, session_provider=session_provider)
        self.private_key = os.getenv("PRIVATE_KEY")  # Do not hardcode secrets
        self._init_mongo()

    def _init_mongo(self) -> None:
        """Initialize Mongo connection and executed_trades collection if pymongo is available."""
        self._executed_trades = None
        self._mongo_client = None
        self._mongo_db = None
        if MongoClient is None:
            self.logger.warning("pymongo not installed; executed_trades will not be logged to MongoDB.")
            return
        try:
            uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
            # Prefer alerts DB name if provided, else portfolio_rebalancer
            db_name = os.getenv("MONGO_DB_NAME", "loki_agents")
            self._mongo_client = MongoClient(uri)
            self._mongo_db = self._mongo_client[db_name]
            self._executed_trades = self._mongo_db["executed_trades"]
        except Exception as e:  # pragma: no cover
            self.logger.error(f"Failed to initialize MongoDB client: {e}")
            self._executed_trades = None

    def execute(self, trades: List[Dict[str, Any]], dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Placeholder executor. In dry_run mode, it only logs the intent.
        - Writes results to MongoDB collection `executed_trades` when available.
        - Triggers alerts after writing each result.
        Returns trade results with a status and optional tx_hash.
        """
        results: List[Dict[str, Any]] = []
        for tr in trades:
            side = tr.get("side", "").lower()
            token = tr.get("token")
            amount = tr.get("amount")

            status = "success"
            reason: Optional[str] = None
            tx_hash: Optional[str] = None

            if dry_run:
                # Treat dry-run as skipped to avoid sending misleading "executed" signals
                status = "skipped"
                reason = "dry_run"
                self.logger.info(
                    f"[DRY RUN] {side.upper()} {amount} {token} on {self.dex} for {self.wallet_address}"
                )
            elif not self.private_key:
                status = "skipped"
                reason = "missing PRIVATE_KEY"
                self.logger.warning(
                    f"Skipping execution due to missing PRIVATE_KEY: {side.upper()} {amount} {token} on {self.dex} for {self.wallet_address}"
                )
            else:
                # Real DEX execution would happen here (e.g., via web3/0x/Uniswap routers)
                try:
                    self.logger.info(
                        f"Submitting {side.upper()} for {amount} {token} on {self.dex} for {self.wallet_address}"
                    )
                    # Placeholder for actual execution; assume success and tx hash
                    tx_hash = "0xPLACEHOLDER"
                    status = "success"
                except Exception as e:  # pragma: no cover
                    status = "failed"
                    reason = str(e)
                    self.logger.error(f"Execution failed: {e}")

            result = {**tr, "status": status, "tx_hash": tx_hash, "reason": reason}
            results.append(result)

            # 1) Write result to MongoDB `executed_trades`
            if self._executed_trades is not None:
                try:
                    pair = (f"USDC→{token}" if side == "buy" else f"{token}→USDC") if token else "N/A"
                    doc = {
                        "timestamp": datetime.now(timezone.utc),
                        "wallet": self.wallet_address,
                        "network": self.network,
                        "dex": self.dex,
                        "token": token,
                        "side": side,
                        "amount": amount,
                        "status": status,
                        "reason": reason,
                        "tx_hash": tx_hash,
                        "trade_summary": pair,
                    }
                    self._executed_trades.insert_one(doc)
                except Exception as e:  # pragma: no cover
                    self.logger.error(f"Failed to write executed_trades doc: {e}")

            # 2) Trigger alerts after writing to MongoDB
            try:
                short = (
                    f"{self.wallet_address[:6]}...{self.wallet_address[-3:]}"
                    if isinstance(self.wallet_address, str) and len(self.wallet_address) > 10
                    else str(self.wallet_address)
                )
                if status == "success":
                    pair = (f"USDC→{token}" if side == "buy" else f"{token}→USDC") if token else "N/A"
                    message = (
                        f"✅ Rebalance executed | Wallet: {short} | Trades: {pair} | Status: SUCCESS"
                    )
                    send_alerts(self.wallet_address, "execution", "success", message)
                elif status == "failed":
                    message = (
                        f"❌ Rebalance failed | Wallet: {short} | Reason: {reason or 'unknown error'}"
                    )
                    send_alerts(self.wallet_address, "execution", "failure", message)
                else:  # skipped
                    message = (
                        f"⚠️ Rebalance skipped | Wallet: {short} | {reason or 'Deviation below threshold'}"
                    )
                    send_alerts(self.wallet_address, "execution", "skipped", message)
            except Exception as e:  # pragma: no cover
                self.logger.error(f"Failed to send alerts: {e}")
        return results


if __name__ == "__main__":
    print("Executor module. Use via scheduler or integrate in your application.")
