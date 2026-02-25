#!/usr/bin/env python3
"""
Integration Test: End-to-End Dry Run
Tests the complete workflow without actual submission
"""

import sys
import os
from pathlib import Path

def test_dry_run():
    print("=" * 60)
    print("Testing ThomasNet End-to-End Workflow (Dry Run)")
    print("=" * 60)
    print("\nThis will test the complete RFQ submission workflow")
    print("without actually submitting to vendors\n")
    
    # Change to ThomasNetAgent directory
    os.chdir(Path(__file__).parent / "ai_agents" / "ThomasNetAgent")
    
    # Find a sample RFQ file
    rfq_file = Path(__file__).parent / "4866eaf56f_RFQ.md"
    
    if not rfq_file.exists():
        print(f"❌ RFQ file not found: {rfq_file}")
        return
    
    print(f"📄 Using RFQ file: {rfq_file.name}\n")
    
    # Run the CLI submit command with dry-run
    import subprocess
    result = subprocess.run(
        [
            "python", "cli.py", "submit",
            "--rfq", str(rfq_file),
            "--dry-run",
            "--headless", "false",
            "--max-vendors", "3"
        ],
        capture_output=True,
        text=True,
        timeout=300  # 5 minutes
    )
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    print("\n" + "=" * 60)
    print(f"Exit Code: {result.returncode}")
    
    if result.returncode == 0:
        print("✅ Dry run completed successfully")
    else:
        print("❌ Dry run failed")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_dry_run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
