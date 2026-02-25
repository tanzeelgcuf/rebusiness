#!/usr/bin/env python3
"""
Instructions to enable Chrome Remote Debugging
"""

print("""
=== Enable Chrome Remote Debugging ===

To use stealth mode, you need to restart Chrome with remote debugging enabled.

STEP 1: Close Chrome completely
   - Cmd+Q (or Chrome > Quit Chrome)

STEP 2: Open Terminal and run:
   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir="/Users/apple/Library/Application Support/Google/Chrome" &

STEP 3: Chrome will open. You can browse normally (e.g., open ThomasNet manually to ensure you're logged in)

STEP 4: Run the test script again:
   python3 test_thomasnet_internal_rfq.py

===================================

The script will now connect to your running Chrome instead of launching a new one!
""")
