from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from main import run_scan

logging.basicConfig(level=logging.INFO)
scheduler = BlockingScheduler(timezone="Asia/Kolkata")

# Indian market: Run at 9:20 AM and 3:10 PM IST (Mon-Fri)
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=9, minute=20))
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=15, minute=10))

# US market close scan: 1:30 AM IST (US market EOD)
scheduler.add_job(run_scan, CronTrigger(day_of_week='mon-fri', hour=1, minute=30))

print("Scheduler running. Press Ctrl+C to exit.")
scheduler.start()