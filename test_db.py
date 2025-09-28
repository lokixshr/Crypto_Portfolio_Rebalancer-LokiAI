from agents.portfolio_rebalancer.db import MongoDBHelper

if __name__ == "__main__":
    db = MongoDBHelper()
    run_id = db.log_run_start(notes="test run")
    db.log_run_finish(run_id, status="success")
    print("✅ Run logged successfully with ID:", run_id)
