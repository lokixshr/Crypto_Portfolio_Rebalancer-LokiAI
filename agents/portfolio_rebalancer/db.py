"""db.py
MongoDB helper providing a simple run/trade store.
"""
from typing import Optional
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
load_dotenv()  # ✅ Ensures .env is read before MongoDBHelper uses it


# Lazy import pymongo to avoid mandatory dependency at import time
try:
    from pymongo import MongoClient, ASCENDING
    from bson import ObjectId
    PYMONGO_AVAILABLE = True
except Exception:
    MongoClient = None  # type: ignore
    ObjectId = None  # type: ignore
    ASCENDING = 1  # type: ignore
    PYMONGO_AVAILABLE = False

from .logger import get_logger


class MongoDBHelper:
    """MongoDB helper for logging runs and trades."""

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        self.logger = get_logger()
        # ✅ Use Atlas connection if provided, otherwise fallback to localhost
        self.uri = uri or os.getenv(
            "MONGO_URI", 
            "mongodb://localhost:27017"  # fallback if .env is missing
        )
        # ✅ Pick DB name from env, or default to "loki_agents"
        self.db_name = db_name or os.getenv("MONGO_DB_NAME", "loki_agents")
        self._client = None
        self._db = None

    def _ensure_client(self) -> None:
        if not PYMONGO_AVAILABLE:
            raise RuntimeError("pymongo is not installed. Please 'pip install pymongo' to use MongoDB logging.")
        if self._client is None:
            self.logger.info(f"Connecting to MongoDB at {self.uri}...")
            self._client = MongoClient(self.uri, tls=True, tlsAllowInvalidCertificates=True)  
            self._db = self._client[self.db_name]
            # Ensure basic indexes
            self._db.runs.create_index([("started_at", ASCENDING)])
            self._db.trades.create_index([("run_id", ASCENDING)])

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None

    def log_run_start(self, started_at: Optional[str] = None, notes: str = "") -> str:
        self._ensure_client()
        started_at = started_at or datetime.now(timezone.utc).isoformat()
        doc = {"started_at": started_at, "finished_at": None, "status": "running", "notes": notes}
        result = self._db.runs.insert_one(doc)
        return str(result.inserted_id)

    def log_run_finish(self, run_id: str, finished_at: Optional[str] = None, status: str = "success") -> None:
        self._ensure_client()
        finished_at = finished_at or datetime.now(timezone.utc).isoformat()
        oid = ObjectId(run_id) if isinstance(run_id, str) else run_id
        self._db.runs.update_one({"_id": oid}, {"$set": {"finished_at": finished_at, "status": status}})

    def log_trade(self, run_id: str, token: str, side: str, amount: float, price: float, value_usd: float, tx_hash: Optional[str]) -> None:
        self._ensure_client()
        oid = ObjectId(run_id) if isinstance(run_id, str) else run_id
        doc = {
            "run_id": oid,
            "token": token,
            "side": side,
            "amount": float(amount),
            "price": float(price),
            "value_usd": float(value_usd),
            "tx_hash": tx_hash,
        }
        self._db.trades.insert_one(doc)
