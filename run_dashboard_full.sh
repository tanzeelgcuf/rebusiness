#!/bin/bash
# run_dashboard_full.sh - Complete dashboard launcher with setup and Chrome management
# Handles environment setup, Chrome launch, and Flask app startup

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  RFQ Dashboard - ThomasNet RFQ Automation Launcher     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 1. Run setup validation
# ============================================================================
echo -e "${BLUE}[1/5]${NC} Running pre-flight checks..."
if [[ ! -f "setup_dashboard.sh" ]]; then
    echo -e "${RED}✗ setup_dashboard.sh not found${NC}"
    exit 1
fi

bash setup_dashboard.sh
echo ""

# ============================================================================
# 2. Detect deployment mode
# ============================================================================
echo -e "${BLUE}[2/5]${NC} Detecting deployment mode..."

# Source env for deployment mode
set +a
[[ -f ".env.dashboard" ]] && source .env.dashboard
set -a

DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-local}"
echo "Deployment mode: ${DEPLOYMENT_MODE}"

# ============================================================================
# 3. Start Chrome if in local mode
# ============================================================================
if [[ "$DEPLOYMENT_MODE" == "local" ]]; then
    echo -e "${BLUE}[3/5]${NC} Starting Chrome for local development..."

    # Find Chrome executable
    CHROME_BIN=""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if [[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
            CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif [[ -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ]]; then
            CHROME_BIN="/Applications/Chromium.app/Contents/MacOS/Chromium"
        fi
    else
        # Linux
        if command -v google-chrome &> /dev/null; then
            CHROME_BIN="google-chrome"
        elif command -v chromium &> /dev/null; then
            CHROME_BIN="chromium"
        elif command -v chromium-browser &> /dev/null; then
            CHROME_BIN="chromium-browser"
        fi
    fi

    if [[ -z "$CHROME_BIN" ]]; then
        echo -e "${YELLOW}⚠ Chrome not found - skipping local Chrome launch${NC}"
        echo "   For local development, manually start Chrome with:"
        echo "   google-chrome --remote-debugging-port=9222"
    else
        echo -e "${GREEN}✓ Found Chrome: $CHROME_BIN${NC}"

        # Check if Chrome is already running on CDP port
        if nc -z 127.0.0.1 9222 2>/dev/null; then
            echo -e "${GREEN}✓ Chrome DevTools Protocol already listening on port 9222${NC}"
        else
            echo "Starting Chrome with remote debugging on port 9222..."

            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS - run in background
                "$CHROME_BIN" --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug &
                CHROME_PID=$!
                echo "Chrome PID: $CHROME_PID"
            else
                # Linux
                nohup "$CHROME_BIN" --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug > /dev/null 2>&1 &
                CHROME_PID=$!
                echo "Chrome PID: $CHROME_PID"
            fi

            # Wait for CDP to be ready
            echo "Waiting for Chrome DevTools Protocol to be ready..."
            for i in {1..30}; do
                if nc -z 127.0.0.1 9222 2>/dev/null; then
                    echo -e "${GREEN}✓ Chrome ready on port 9222${NC}"
                    break
                fi
                echo -n "."
                sleep 1
            done
            echo ""

            # Save PID for cleanup
            echo "$CHROME_PID" > /tmp/dashboard_chrome.pid
        fi
    fi
else
    echo -e "${BLUE}[3/5]${NC} Server mode detected - Chrome not launched (use headless)"
fi

echo ""

# ============================================================================
# 4. Setup Python environment
# ============================================================================
echo -e "${BLUE}[4/5]${NC} Setting up Python environment..."

# Activate virtual environment if it exists
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
fi

# Export Flask variables
export PYTHONUNBUFFERED=1
export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_APP="dashboard/app.py"
export FLASK_DEBUG="${FLASK_DEBUG:-True}"

echo ""

# ============================================================================
# 5. Start Flask Dashboard
# ============================================================================
echo -e "${BLUE}[5/5]${NC} Starting Flask Dashboard..."
echo ""

DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"
DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"

echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Dashboard is starting...                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  URL: ${BLUE}http://localhost:${DASHBOARD_PORT}${NC}"
echo -e "  API: ${BLUE}http://localhost:${DASHBOARD_PORT}/api${NC}"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

# Start Flask app
cd dashboard
python3 app.py --host "$DASHBOARD_HOST" --port "$DASHBOARD_PORT"

# Cleanup on exit
trap "
    echo ''
    echo -e '${YELLOW}Cleaning up...${NC}'
    if [[ -f /tmp/dashboard_chrome.pid ]]; then
        CHROME_PID=\$(cat /tmp/dashboard_chrome.pid)
        kill \$CHROME_PID 2>/dev/null || true
        rm /tmp/dashboard_chrome.pid
    fi
    exit 0
" EXIT INT TERM
