#!/usr/bin/env python3
"""
Weekly RFQ & ThomasNet Automation Runner
Runs continuous automation for 7 days with enhanced monitoring and error recovery.

Usage:
    # Start 7-day automation
    python3 run_weekly_automation.py
    
    # Test mode (one cycle then exit)
    python3 run_weekly_automation.py --test-mode
    
    # Custom duration
    python3 run_weekly_automation.py --duration-days 3
    
    # Resume from previous run
    python3 run_weekly_automation.py --resume
"""

import os
import sys
import time
import json
import logging
import argparse
import traceback
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
log_dir = Path('logs/weekly_automation')
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"weekly_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Status file for tracking
STATUS_FILE = 'automation_status.json'

class WeeklyAutomation:
    """Manages week-long continuous automation with monitoring and recovery."""
    
    def __init__(self, duration_days=7, check_interval_minutes=180, 
                 max_vendors=5, test_mode=False):
        self.duration_days = duration_days
        self.check_interval_minutes = check_interval_minutes
        self.max_vendors = max_vendors
        self.test_mode = test_mode
        
        self.start_time = None
        self.end_time = None
        self.cycles_completed = 0
        self.rfqs_generated = 0
        self.vendors_contacted = 0
        self.errors = []
        
        self.status_file = Path(STATUS_FILE)
        
    def initialize(self):
        """Initialize the automation run."""
        logger.info("="*80)
        logger.info("WEEKLY RFQ & THOMASNET AUTOMATION")
        logger.info("="*80)
        logger.info(f"Duration: {self.duration_days} days")
        logger.info(f"Check interval: {self.check_interval_minutes} minutes")
        logger.info(f"Max vendors per RFQ: {self.max_vendors}")
        logger.info(f"Test mode: {self.test_mode}")
        logger.info(f"Log file: {log_file}")
        logger.info("="*80)
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(days=self.duration_days)
        
        logger.info(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"End time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save initial status
        self.save_status('RUNNING')
        
    def save_status(self, status='RUNNING'):
        """Save current automation status to JSON file."""
        now = datetime.now()
        elapsed = (now - self.start_time).total_seconds() / 3600 if self.start_time else 0
        remaining = (self.end_time - now).total_seconds() / 3600 if self.end_time else 0
        
        status_data = {
            'status': status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'current_time': now.isoformat(),
            'elapsed_hours': round(elapsed, 2),
            'remaining_hours': round(max(0, remaining), 2),
            'duration_days': self.duration_days,
            'check_interval_minutes': self.check_interval_minutes,
            'cycles_completed': self.cycles_completed,
            'rfqs_generated': self.rfqs_generated,
            'vendors_contacted': self.vendors_contacted,
            'test_mode': self.test_mode,
            'last_update': now.isoformat(),
            'log_file': str(log_file),
            'errors': self.errors[-10:]  # Keep last 10 errors
        }
        
        with open(self.status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
            
    def send_heartbeat(self):
        """Send heartbeat signal to confirm automation is alive."""
        logger.info(f"💓 HEARTBEAT - Cycle {self.cycles_completed} - "
                   f"Elapsed: {(datetime.now() - self.start_time).total_seconds() / 3600:.1f}h")
        self.save_status()
        
    def run_automation_cycle(self):
        """Run one complete automation cycle."""
        logger.info("\n" + "="*80)
        logger.info(f"STARTING CYCLE {self.cycles_completed + 1}")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        try:
            # Import here to avoid issues if modules not available at startup
            from run_complete_automation import find_unprocessed_rfqs, process_rfq_file, mark_as_processed
            from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
            
            # Find unprocessed RFQs
            logger.info("Step 1: Finding unprocessed RFQs...")
            unprocessed = find_unprocessed_rfqs()
            
            if unprocessed:
                logger.info(f"Found {len(unprocessed)} unprocessed RFQ(s)")
                
                # Initialize ThomasNet agent
                agent = ThomasNetAgent()
                
                # Process each RFQ
                for i, rfq_path in enumerate(unprocessed, 1):
                    logger.info(f"\nProcessing RFQ {i}/{len(unprocessed)}: {os.path.basename(rfq_path)}")
                    
                    result = process_rfq_file(rfq_path, agent, max_vendors=self.max_vendors)
                    
                    if result.get('success'):
                        mark_as_processed(rfq_path)
                        self.rfqs_generated += 1
                        self.vendors_contacted += result.get('vendors_contacted', 0)
                        logger.info(f"✅ Successfully processed: {os.path.basename(rfq_path)}")
                    else:
                        error_msg = f"Failed to process {rfq_path}: {result.get('error')}"
                        logger.error(f"❌ {error_msg}")
                        self.errors.append({
                            'time': datetime.now().isoformat(),
                            'error': error_msg
                        })
                    
                    # Small delay between RFQs
                    if i < len(unprocessed):
                        time.sleep(5)
            else:
                logger.info("No new RFQs to process in this cycle")
            
            # Update cycle count
            self.cycles_completed += 1
            
            logger.info("\n" + "="*80)
            logger.info(f"CYCLE {self.cycles_completed} COMPLETE")
            logger.info(f"Total RFQs processed: {self.rfqs_generated}")
            logger.info(f"Total vendors contacted: {self.vendors_contacted}")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            error_msg = f"Cycle failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            self.errors.append({
                'time': datetime.now().isoformat(),
                'error': error_msg,
                'traceback': traceback.format_exc()
            })
            
            return False
            
    def check_system_health(self):
        """Check system health (disk space, memory, etc.)."""
        try:
            # Check disk space
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            
            if free_gb < 1:
                logger.warning(f"⚠️  Low disk space: {free_gb}GB remaining")
                return False
            
            logger.info(f"💾 Disk space: {free_gb}GB free")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return True  # Don't stop automation for health check failures
            
    def run(self):
        """Run the automation for the configured duration."""
        self.initialize()
        
        if self.test_mode:
            logger.info("🧪 TEST MODE - Running single cycle")
            success = self.run_automation_cycle()
            self.save_status('COMPLETED' if success else 'FAILED')
            return
        
        # Main automation loop
        last_heartbeat = datetime.now()
        heartbeat_interval = timedelta(minutes=30)
        
        try:
            while datetime.now() < self.end_time:
                # Send heartbeat
                if datetime.now() - last_heartbeat >= heartbeat_interval:
                    self.send_heartbeat()
                    last_heartbeat = datetime.now()
                
                # Check system health
                if not self.check_system_health():
                    logger.warning("System health check failed, but continuing...")
                
                # Run automation cycle
                success = self.run_automation_cycle()
                
                if not success:
                    logger.warning("Cycle failed, waiting 5 minutes before retry...")
                    time.sleep(300)  # 5 minute cooldown
                    continue
                
                # Calculate time until next cycle
                time_remaining = (self.end_time - datetime.now()).total_seconds()
                sleep_time = min(self.check_interval_minutes * 60, time_remaining)
                
                if sleep_time <= 0:
                    break
                
                # Save status
                self.save_status('RUNNING')
                
                # Sleep until next cycle
                next_cycle = datetime.now() + timedelta(seconds=sleep_time)
                logger.info(f"\n💤 Sleeping until {next_cycle.strftime('%Y-%m-%d %H:%M:%S')} "
                           f"({sleep_time/60:.1f} minutes)")
                time.sleep(sleep_time)
            
            # Automation completed
            logger.info("\n" + "="*80)
            logger.info("✅ WEEKLY AUTOMATION COMPLETED SUCCESSFULLY")
            logger.info("="*80)
            logger.info(f"Duration: {self.duration_days} days")
            logger.info(f"Cycles completed: {self.cycles_completed}")
            logger.info(f"RFQs processed: {self.rfqs_generated}")
            logger.info(f"Vendors contacted: {self.vendors_contacted}")
            logger.info(f"Errors encountered: {len(self.errors)}")
            logger.info("="*80)
            
            self.save_status('COMPLETED')
            
            # Generate final report
            self.generate_final_report()
            
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Automation stopped by user")
            self.save_status('STOPPED')
            
        except Exception as e:
            logger.error(f"\n\n❌ Automation failed: {e}")
            logger.error(traceback.format_exc())
            self.save_status('FAILED')
            
    def generate_final_report(self):
        """Generate final summary report."""
        report_file = f"automation_weekly_summary_{datetime.now().strftime('%Y%m%d')}.json"
        
        report = {
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_days': self.duration_days,
            'cycles_completed': self.cycles_completed,
            'rfqs_generated': self.rfqs_generated,
            'vendors_contacted': self.vendors_contacted,
            'success_rate': round((self.cycles_completed - len(self.errors)) / max(self.cycles_completed, 1) * 100, 2),
            'errors': self.errors,
            'log_file': str(log_file)
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n📊 Final report saved to: {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Weekly RFQ & ThomasNet Automation")
    parser.add_argument('--duration-days', type=int, default=7,
                       help='Total days to run (default: 7)')
    parser.add_argument('--check-interval', type=int, default=180,
                       help='Minutes between checks (default: 180 = 3 hours)')
    parser.add_argument('--max-vendors', type=int, default=5,
                       help='Maximum vendors per RFQ (default: 5)')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run single cycle then exit')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous run')
    
    args = parser.parse_args()
    
    # Create automation instance
    automation = WeeklyAutomation(
        duration_days=args.duration_days,
        check_interval_minutes=args.check_interval,
        max_vendors=args.max_vendors,
        test_mode=args.test_mode
    )
    
    # Run automation
    automation.run()


if __name__ == "__main__":
    main()
