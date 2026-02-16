#!/bin/bash

echo "==================================================="
echo "   Starting Chrome (Dedicated Automation Profile)"
echo "==================================================="

# Define a persistent profile directory in user's home
PROFILE_DIR="$HOME/chrome-automation-profile"
mkdir -p "$PROFILE_DIR"

# 1. Cleanup specific automation instances
echo "1. Checking for existing automation instances..."
lsof -ti:9222 | xargs kill -9 2>/dev/null

# 2. Start with Custom Profile
echo "2. Launching Chrome..."
echo "   Profile: $PROFILE_DIR"

nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2>&1 &

# 3. Verification
sleep 4
if lsof -i :9222 > /dev/null; then
    echo "==================================================="
    echo "✅ SUCCESS: Chrome is listening on port 9222!"
    echo "   IMPORTANT:"
    echo "   1. A new 'clean' Chrome window has opened."
    echo "   2. Log in to ThomasNet.com in this window."
    echo "      (Your login will be saved here for next time)"
    echo "   3. Run your Dashboard automation."
    echo "==================================================="
else
    echo "==================================================="
    echo "❌ ERROR: Still cannot start Chrome on port 9222."
    echo "   Please restart your computer."
    echo "==================================================="
fi
