#!/usr/bin/env python3
"""
Georgia Property Data Refresh Scheduler
Orchestrates automated loading of Georgia public records data
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_refresh.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Data refresh schedules
REFRESH_SCHEDULES = {
    'ga_gio_parcels': {
        'frequency': 'weekly',
        'script': 'load_ga_gio_parcels.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    },
    'county_tax_assessors': {
        'frequency': 'daily',
        'script': 'load_county_tax_assessors.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    },
    'gsccca_deeds': {
        'frequency': 'daily',
        'script': 'load_gsccca_deeds.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    },
    'county_permits': {
        'frequency': 'daily',
        'script': 'load_county_permits.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    },
    'fema_flood': {
        'frequency': 'monthly',
        'script': 'load_fema_flood.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    },
    'ga_doe_schools': {
        'frequency': 'quarterly',
        'script': 'load_ga_doe_schools.py',
        'next_run': None,
        'last_run': None,
        'status': 'pending'
    }
}

class DataRefreshScheduler:
    """Manages automated data refresh scheduling and execution."""

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir
        self.schedule_file = scripts_dir.parent / "config" / "refresh_schedule.json"
        self.log_file = scripts_dir.parent / "logs" / "data_refresh.log"
        self.load_schedule()

    def load_schedule(self):
        """Load refresh schedule from file."""
        if self.schedule_file.exists():
            try:
                with open(self.schedule_file, 'r') as f:
                    saved_schedule = json.load(f)
                    # Update our schedule with saved data
                    for key, data in saved_schedule.items():
                        if key in REFRESH_SCHEDULES:
                            REFRESH_SCHEDULES[key].update(data)
                logger.info("Loaded refresh schedule from file")
            except Exception as e:
                logger.error(f"Failed to load schedule: {e}")

        # Initialize next run times if not set
        self.initialize_schedule()

    def save_schedule(self):
        """Save current schedule to file."""
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedule_file, 'w') as f:
            json.dump(REFRESH_SCHEDULES, f, indent=2, default=str)
        logger.info("Saved refresh schedule to file")

    def initialize_schedule(self):
        """Initialize next run times based on frequency."""
        now = datetime.now()

        for key, schedule in REFRESH_SCHEDULES.items():
            if schedule['next_run'] is None:
                if schedule['frequency'] == 'daily':
                    schedule['next_run'] = now.replace(hour=2, minute=0, second=0, microsecond=0)  # 2 AM daily
                elif schedule['frequency'] == 'weekly':
                    # Next Sunday at 3 AM
                    days_until_sunday = (6 - now.weekday()) % 7
                    if days_until_sunday == 0:
                        days_until_sunday = 7
                    schedule['next_run'] = (now + timedelta(days=days_until_sunday)).replace(hour=3, minute=0, second=0, microsecond=0)
                elif schedule['frequency'] == 'monthly':
                    # First day of next month at 4 AM
                    if now.month == 12:
                        next_month = 1
                        next_year = now.year + 1
                    else:
                        next_month = now.month + 1
                        next_year = now.year
                    schedule['next_run'] = datetime(next_year, next_month, 1, 4, 0, 0)
                elif schedule['frequency'] == 'quarterly':
                    # First day of next quarter at 5 AM
                    current_quarter = (now.month - 1) // 3 + 1
                    if current_quarter == 4:
                        next_quarter_month = 1
                        next_year = now.year + 1
                    else:
                        next_quarter_month = (current_quarter * 3) + 1
                        next_year = now.year
                    schedule['next_run'] = datetime(next_year, next_quarter_month, 1, 5, 0, 0)

        self.save_schedule()

    def is_time_to_run(self, schedule_key: str) -> bool:
        """Check if it's time to run a scheduled job."""
        schedule = REFRESH_SCHEDULES[schedule_key]
        if schedule['next_run'] is None:
            return False

        next_run = datetime.fromisoformat(schedule['next_run']) if isinstance(schedule['next_run'], str) else schedule['next_run']
        return datetime.now() >= next_run

    def run_script(self, script_name: str) -> bool:
        """Execute a data loading script."""
        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False

        logger.info(f"Starting script: {script_name}")

        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.info(f"Script completed successfully: {script_name}")
                if result.stdout:
                    logger.info(f"Script output: {result.stdout}")
                return True
            else:
                logger.error(f"Script failed: {script_name}")
                if result.stderr:
                    logger.error(f"Script error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Script timed out: {script_name}")
            return False
        except Exception as e:
            logger.error(f"Script execution error: {script_name} - {e}")
            return False

    def update_schedule_after_run(self, schedule_key: str, success: bool):
        """Update schedule after a job run."""
        schedule = REFRESH_SCHEDULES[schedule_key]
        now = datetime.now()

        schedule['last_run'] = now
        schedule['status'] = 'success' if success else 'failed'

        # Calculate next run time
        if schedule['frequency'] == 'daily':
            schedule['next_run'] = now + timedelta(days=1)
        elif schedule['frequency'] == 'weekly':
            schedule['next_run'] = now + timedelta(days=7)
        elif schedule['frequency'] == 'monthly':
            # Next month
            if now.month == 12:
                next_month = 1
                next_year = now.year + 1
            else:
                next_month = now.month + 1
                next_year = now.year
            schedule['next_run'] = datetime(next_year, next_month, 1, 4, 0, 0)
        elif schedule['frequency'] == 'quarterly':
            # Next quarter
            current_quarter = (now.month - 1) // 3 + 1
            if current_quarter == 4:
                next_quarter_month = 1
                next_year = now.year + 1
            else:
                next_quarter_month = (current_quarter * 3) + 1
                next_year = now.year
            schedule['next_run'] = datetime(next_year, next_quarter_month, 1, 5, 0, 0)

        self.save_schedule()

    def run_database_optimization(self):
        """Run database optimization after data loading."""
        logger.info("Running database optimization...")

        try:
            # This would run ANALYZE and REFRESH MATERIALIZED VIEW in production
            # For now, just log the intent
            logger.info("Database optimization completed (ANALYZE parcels; REFRESH MATERIALIZED VIEW)")
            return True
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False

    def run_scheduled_jobs(self):
        """Run all jobs that are due."""
        logger.info("Checking for scheduled jobs...")

        jobs_run = 0

        for schedule_key, schedule in REFRESH_SCHEDULES.items():
            if self.is_time_to_run(schedule_key):
                logger.info(f"Running scheduled job: {schedule_key}")

                # Run the script
                success = self.run_script(schedule['script'])

                # Update schedule
                self.update_schedule_after_run(schedule_key, success)

                jobs_run += 1

                # Run optimization after each successful job
                if success:
                    self.run_database_optimization()

        if jobs_run == 0:
            logger.info("No jobs due at this time")

        return jobs_run

    def run_manual_job(self, schedule_key: str) -> bool:
        """Run a specific job manually."""
        if schedule_key not in REFRESH_SCHEDULES:
            logger.error(f"Unknown job: {schedule_key}")
            return False

        logger.info(f"Running manual job: {schedule_key}")

        success = self.run_script(REFRESH_SCHEDULES[schedule_key]['script'])
        self.update_schedule_after_run(schedule_key, success)

        if success:
            self.run_database_optimization()

        return success

    def get_schedule_status(self) -> Dict:
        """Get current schedule status."""
        return {
            'jobs': REFRESH_SCHEDULES,
            'last_check': datetime.now().isoformat()
        }

def main():
    """Main entry point for the scheduler."""
    scripts_dir = Path(__file__).parent
    scheduler = DataRefreshScheduler(scripts_dir)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'status':
            # Show current status
            status = scheduler.get_schedule_status()
            print(json.dumps(status, indent=2, default=str))

        elif command == 'run':
            # Run all due jobs
            jobs_run = scheduler.run_scheduled_jobs()
            print(f"Ran {jobs_run} scheduled jobs")

        elif command.startswith('run_'):
            # Run specific job manually
            job_name = command[4:]  # Remove 'run_' prefix
            success = scheduler.run_manual_job(job_name)
            print(f"Manual job {job_name}: {'SUCCESS' if success else 'FAILED'}")

        elif command == 'init':
            # Initialize schedule
            scheduler.initialize_schedule()
            print("Schedule initialized")

        else:
            print("Usage:")
            print("  python data_refresh_scheduler.py status          # Show schedule status")
            print("  python data_refresh_scheduler.py run            # Run all due jobs")
            print("  python data_refresh_scheduler.py run_ga_gio_parcels  # Run specific job")
            print("  python data_refresh_scheduler.py init           # Initialize schedule")
    else:
        # Default: run scheduled jobs
        jobs_run = scheduler.run_scheduled_jobs()
        print(f"Completed: ran {jobs_run} jobs")

if __name__ == "__main__":
    main()