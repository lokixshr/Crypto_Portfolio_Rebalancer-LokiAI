import os
import smtplib
import requests
from email.mime.text import MIMEText
from pymongo import MongoClient
from datetime import datetime, timezone
from pathlib import Path

# Ensure .env variables are loaded before accessing os.getenv
from dotenv import load_dotenv
load_dotenv()

# Load config.json (path relative to this file for reliability)
import json
CONFIG_PATH = Path(__file__).with_name("config.json")
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    config = json.load(f)

alerts_config = config["alerts"]

# MongoDB connection (env-overridable)
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
mongo_db_name = os.getenv("MONGO_DB_NAME", "loki_agents")
client = MongoClient(mongo_uri)
db = client[mongo_db_name]
alerts_collection = db["rebalance_alerts"]

# --- Telegram ---
def send_telegram_alert(message: str):
    try:
        url = f"https://api.telegram.org/bot{alerts_config['telegram_bot_token']}/sendMessage"
        data = {"chat_id": alerts_config["telegram_chat_id"], "text": message}
        r = requests.post(url, data=data)
        r.raise_for_status()
        return "sent", None
    except Exception as e:
        return "failed", str(e)

# --- Discord ---
def send_discord_alert(message: str):
    try:
        data = {"content": message}
        r = requests.post(alerts_config["discord_webhook_url"], json=data)
        r.raise_for_status()
        return "sent", None
    except Exception as e:
        return "failed", str(e)

# --- Email ---
def send_email_alert(message: str, subject="LokiAI Rebalance Alert"):
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = alerts_config["email_user"]
        msg["To"] = alerts_config["email_to"]

        server = smtplib.SMTP(alerts_config["email_smtp"], 587)
        server.starttls()
        server.login(alerts_config["email_user"], alerts_config["email_pass"])
        server.sendmail(alerts_config["email_user"], alerts_config["email_to"], msg.as_string())
        server.quit()
        return "sent", None
    except Exception as e:
        return "failed", str(e)

# --- Logging to Mongo ---
def log_alert(wallet, event_type, alert_type, channel, status, reason, message):
    alerts_collection.insert_one({
        "timestamp": datetime.now(timezone.utc),
        "wallet": wallet,
        "event_type": event_type,
        "alert_type": alert_type,
        "message": message,
        "channel": channel,
        "status": status,
        "reason": reason
    })

# --- Example trigger ---
def send_alerts(wallet, event_type, alert_type, message):
    for channel in alerts_config["channels"]:
        if channel == "telegram":
            status, reason = send_telegram_alert(message)
            log_alert(wallet, event_type, alert_type, "telegram", status, reason, message)
        elif channel == "discord":
            status, reason = send_discord_alert(message)
            log_alert(wallet, event_type, alert_type, "discord", status, reason, message)
        elif channel == "email":
            status, reason = send_email_alert(message)
            log_alert(wallet, event_type, alert_type, "email", status, reason, message)

if __name__ == "__main__":
    # Example test run
    send_alerts(
        wallet="0x8BBFa86f2766fd05220f319a4d122C97fBC4B529",
        event_type="execution",
        alert_type="success",
        message="✅ Rebalance executed | Trades: ETH→USDC | Status: SUCCESS"
    )
