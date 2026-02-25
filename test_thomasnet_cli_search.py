#!/usr/bin/env python3
"""
Quick Test: ThomasNet CLI Test Search
Tests the search functionality without authentication
"""

import sys
import os
from pathlib import Path

# Add ai_agents to path
sys.path.insert(0, str(Path(__file__).parent / "ai_agents"))

def test_cli_search():
    print("=" * 60)
    print("Testing ThomasNet CLI - Test Search Command")
    print("=" * 60)
    print("\nThis will test the CLI search command")
    print("Note: This requires authentication to work properly\n")
    
    # Import and run CLI test-search command
    os.chdir(Path(__file__).parent / "ai_agents" / "ThomasNetAgent")
    
    # Run the CLI command
    import subprocess
    result = subprocess.run(
        ["python", "cli.py", "test-search", "industrial fasteners", "--headless", "false"],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    print("\n" + "=" * 60)
    print(f"Exit Code: {result.returncode}")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_cli_search()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
