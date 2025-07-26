#!/usr/bin/env python3
"""
Cron script for running automatic assignment process
Run this via cron every hour: 0 * * * * /path/to/venv/bin/python /path/to/run_assignment_cron.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.assignment_service import AssignmentService
from app.services.review_service import ReviewService
from app.utils.logger import get_logger
from app.database import init_db
from datetime import datetime

logger = get_logger('assignment_cron')


def main():
    """Main cron job function"""
    logger.info(f"Starting assignment cron job at {datetime.utcnow()}")
    
    try:
        # Initialize database
        init_db()
        
        # Process pending game assignments
        assignment_service = AssignmentService()
        assignment_service.process_pending_games()
        
        # Send review reminders
        review_service = ReviewService()
        review_service.send_review_reminders()
        
        logger.info("Assignment cron job completed successfully")
        
    except Exception as e:
        logger.error(f"Error in assignment cron job: {str(e)}")
        raise


if __name__ == "__main__":
    main()