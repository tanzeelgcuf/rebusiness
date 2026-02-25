#!/bin/bash
# Quick Start Script for Complete Test

echo "=================================="
echo " RFQ Automation Complete Test"
echo "=================================="
echo ""
echo "This will start:"
echo "  1. Dashboard server (port 5000)"
echo "  2. Chrome with remote debugging"
echo "  3. Complete automation test"
echo ""

# Check if dashboard is already running
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ Dashboard already running on port 5000"
else
    echo "Starting dashboard..."
    cd dashboard && python3 app.py > ../dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo "✓ Dashboard started (PID: $DASHBOARD_PID)"
    sleep 3
fi

# Check if Chrome debugging is running
if lsof -Pi :9222 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ Chrome debugging already running on port 9222"
else
    echo ""
    echo "Starting Chrome with remote debugging..."
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
      --remote-debugging-port=9222 \
      --user-data-dir="/tmp/chrome-debug" \
      > /dev/null 2>&1 &
    echo "✓ Chrome started"
    echo ""
    echo "⚠️  IMPORTANT: Sign in to ThomasNet in the Chrome window!"
    echo "   Go to: https://www.thomasnet.com"
    echo ""
    read -p "Press ENTER when signed in..."
fi

echo ""
echo "=================================="
echo " Ready to Run Test!"
echo "=================================="
echo ""
echo "Dashboard: http://localhost:5000"
echo ""
echo "Open the dashboard in your browser to monitor:"
echo "  - Solicitations being scraped"
echo "  - RFQs being generated"
echo "  - Vendors being contacted"
echo ""
read -p "Press ENTER to start the complete test..."

# Run the test
cd ..
python3 test_complete_pipeline.py

echo ""
echo "=================================="
echo " Test Complete!"
echo "=================================="
echo ""
echo "Dashboard is still running at: http://localhost:5000"
echo ""
echo "To stop the dashboard:"
echo "  lsof -ti:5000 | xargs kill"
echo ""
