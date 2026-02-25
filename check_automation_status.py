#!/usr/bin/env python3
"""
Automation Status Checker
Displays current status of the weekly RFQ & ThomasNet automation.

Usage:
    python3 check_automation_status.py
    
    # Continuous monitoring (refresh every 60 seconds)
    python3 check_automation_status.py --watch
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

STATUS_FILE = 'automation_status.json'

def format_duration(hours):
    """Format hours into human-readable duration."""
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    elif hours < 24:
        return f"{hours:.1f} hours"
    else:
        days = int(hours / 24)
        remaining_hours = hours % 24
        return f"{days} days, {remaining_hours:.1f} hours"

def get_status_emoji(status):
    """Get emoji for status."""
    status_map = {
        'RUNNING': '🟢',
        'COMPLETED': '✅',
        'STOPPED': '⏸️',
        'FAILED': '❌',
        'NOT_RUNNING': '⚪'
    }
    return status_map.get(status, '❓')

def check_automation_status():
    """Read and display automation status."""
    status_file = Path(STATUS_FILE)
    
    # Header
    print("\n" + "="*70)
    print("  RFQ & THOMASNET AUTOMATION STATUS")
    print("="*70)
    print()
    
    # Check if status file exists
    if not status_file.exists():
        print(f"{get_status_emoji('NOT_RUNNING')} Status: NOT RUNNING")
        print()
        print("No active automation detected.")
        print(f"Status file not found: {STATUS_FILE}")
        print()
        print("To start automation:")
        print("  python3 run_weekly_automation.py")
        print()
        print("="*70)
        return False
    
    # Read status
    try:
        with open(status_file, 'r') as f:
            status = json.load(f)
    except Exception as e:
        print(f"❌ Error reading status file: {e}")
        return False
    
    # Display status
    current_status = status.get('status', 'UNKNOWN')
    print(f"{get_status_emoji(current_status)} Status: {current_status}")
    print()
    
    # Time information
    if status.get('start_time'):
        start_time = datetime.fromisoformat(status['start_time'])
        print(f"🕐 Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if status.get('end_time'):
        end_time = datetime.fromisoformat(status['end_time'])
        print(f"🏁 End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if status.get('current_time'):
        current_time = datetime.fromisoformat(status['current_time'])
        print(f"⏰ Last Update: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print()
    
    # Duration information
    elapsed = status.get('elapsed_hours', 0)
    remaining = status.get('remaining_hours', 0)
    duration_days = status.get('duration_days', 7)
    
    if current_status == 'RUNNING':
        print(f"⏳ Elapsed: {format_duration(elapsed)}")
        print(f"⌛ Remaining: {format_duration(remaining)}")
        
        # Progress bar
        total_hours = duration_days * 24
        progress_percent = min(100, (elapsed / total_hours) * 100)
        bar_length = 40
        filled = int(bar_length * progress_percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"📊 Progress: [{bar}] {progress_percent:.1f}%")
    elif current_status == 'COMPLETED':
        print(f"✅ Total duration: {format_duration(elapsed)}")
    
    print()
    
    # Statistics
    print("📈 Statistics:")
    print(f"   Cycles completed: {status.get('cycles_completed', 0)}")
    print(f"   RFQs processed: {status.get('rfqs_generated', 0)}")
    print(f"   Vendors contacted: {status.get('vendors_contacted', 0)}")
    
    # Calculate averages
    cycles = status.get('cycles_completed', 0)
    if cycles > 0:
        avg_rfqs = status.get('rfqs_generated', 0) / cycles
        avg_vendors = status.get('vendors_contacted', 0) / cycles
        print(f"   Avg RFQs/cycle: {avg_rfqs:.1f}")
        print(f"   Avg vendors/cycle: {avg_vendors:.1f}")
    
    print()
    
    # Errors
    errors = status.get('errors', [])
    if errors:
        print(f"⚠️  Recent Errors: {len(errors)}")
        print()
        for i, error in enumerate(errors[-3:], 1):  # Show last 3 errors
            error_time = error.get('time', 'Unknown time')
            error_msg = error.get('error', 'Unknown error')
            print(f"   {i}. [{error_time}]")
            print(f"      {error_msg[:70]}...")
        print()
    
    # Configuration
    print("⚙️  Configuration:")
    print(f"   Duration: {duration_days} days")
    print(f"   Check interval: {status.get('check_interval_minutes', 180)} minutes")
    print(f"   Test mode: {status.get('test_mode', False)}")
    print()
    
    # Log file
    if status.get('log_file'):
        log_file = status['log_file']
        if Path(log_file).exists():
            log_size = Path(log_file).stat().st_size / 1024  # KB
            print(f"📝 Log File: {log_file}")
            print(f"   Size: {log_size:.1f} KB")
            print()
            print(f"   View logs: tail -f {log_file}")
        else:
            print(f"📝 Log File: {log_file} (not found)")
    
    print()
    
    # Next steps
    if current_status == 'RUNNING':
        print("🔧 Management:")
        print(f"   Stop automation: kill $(cat automation.pid)")
        print(f"   View live logs: tail -f {status.get('log_file', 'weekly_automation.log')}")
    elif current_status == 'STOPPED' or current_status == 'FAILED':
        print("🔧 Management:")
        print("   Resume automation: python3 run_weekly_automation.py --resume")
        print("   Start fresh: python3 run_weekly_automation.py")
    elif current_status == 'COMPLETED':
        print("🎉 Automation completed successfully!")
        print()
        print("   View summary: cat automation_weekly_summary_*.json")
        print("   Start new run: python3 run_weekly_automation.py")
    
    print()
    print("="*70)
    print()
    
    return True

def watch_mode(interval=60):
    """Continuously monitor automation status."""
    print("👀 Watching automation status (Ctrl+C to stop)")
    print(f"Refresh interval: {interval} seconds")
    
    try:
        while True:
            # Clear screen (works on Unix-like systems)
            os.system('clear' if os.name == 'posix' else 'cls')
            
            check_automation_status()
            
            print(f"Refreshing in {interval} seconds...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 Stopped monitoring")

def main():
    parser = argparse.ArgumentParser(description="Check automation status")
    parser.add_argument('--watch', action='store_true',
                       help='Continuously monitor status')
    parser.add_argument('--interval', type=int, default=60,
                       help='Refresh interval for watch mode (seconds)')
    
    args = parser.parse_args()
    
    if args.watch:
        watch_mode(args.interval)
    else:
        check_automation_status()

if __name__ == "__main__":
    main()
