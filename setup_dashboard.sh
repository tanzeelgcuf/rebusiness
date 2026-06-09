#!/bin/bash
# setup_dashboard.sh - Dashboard pre-flight validation and configuration
# Validates environment, dependencies, and database before running dashboard

set -e

echo "🚀 RFQ Dashboard Setup & Validation"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track validation status
MISSING_VARS=()
MISSING_DEPS=()
WARNINGS=()

# ============================================================================
# 1. Check Python and Virtual Environment
# ============================================================================
echo -e "${BLUE}[1/6]${NC} Checking Python environment..."

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"

# Check if in virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    if [[ -d ".venv" ]]; then
        echo -e "${YELLOW}⚠ Virtual environment not activated, activating...${NC}"
        source .venv/bin/activate
    else
        echo -e "${YELLOW}⚠ No virtual environment detected${NC}"
        WARNINGS+=("Consider creating a virtual environment: python3 -m venv .venv")
    fi
fi

echo ""

# ============================================================================
# 2. Check Required Dependencies
# ============================================================================
echo -e "${BLUE}[2/6]${NC} Checking Python dependencies..."

REQUIRED_PACKAGES=("flask" "flask_cors" "playwright" "python-dotenv" "pydantic")

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import ${package//-/_}" 2>/dev/null; then
        echo -e "${GREEN}✓ ${package}${NC}"
    else
        echo -e "${RED}✗ ${package}${NC}"
        MISSING_DEPS+=("$package")
    fi
done

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo -e "${RED}Missing dependencies: ${MISSING_DEPS[*]}${NC}"
    echo "Install with: pip install -r requirements.txt"
    exit 1
fi

echo ""

# ============================================================================
# 3. Load and Validate Environment Variables
# ============================================================================
echo -e "${BLUE}[3/6]${NC} Checking configuration (.env.dashboard)..."

if [[ ! -f ".env.dashboard" ]]; then
    echo -e "${YELLOW}✗ .env.dashboard not found${NC}"
    echo "Creating from template..."
    if [[ -f ".env.dashboard.example" ]]; then
        cp .env.dashboard.example .env.dashboard
        echo -e "${GREEN}✓ Created .env.dashboard from template${NC}"
    else
        echo -e "${YELLOW}⚠ No template found, using defaults${NC}"
    fi
fi

# Source the environment file
if [[ -f ".env.dashboard" ]]; then
    set +a
    source .env.dashboard
    set -a
    echo -e "${GREEN}✓ Loaded .env.dashboard${NC}"
fi

# Check required environment variables
REQUIRED_VARS=("THOMASNET_EMAIL" "THOMASNET_PASSWORD" "CAPSOLVER_API_KEY" "TWO_CAPTCHA_API_KEY")
OPTIONAL_VARS=("THOMASNET_PROXY_SERVER" "DEPLOYMENT_MODE")

for var in "${REQUIRED_VARS[@]}"; do
    value=$(eval echo \$$var)
    if [[ -z "$value" ]] || [[ "$value" == *"your_"* ]]; then
        echo -e "${YELLOW}✗ ${var} not configured${NC}"
        MISSING_VARS+=("$var")
    else
        # Mask the value for security
        masked_value="${value:0:4}...${value: -4}"
        echo -e "${GREEN}✓ ${var} = ${masked_value}${NC}"
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo -e "${RED}Missing required configuration: ${MISSING_VARS[*]}${NC}"
    echo "Edit .env.dashboard and fill in the required values"
    exit 1
fi

echo ""

# ============================================================================
# 4. Check Database
# ============================================================================
echo -e "${BLUE}[4/6]${NC} Checking database..."

DB_PATH="${DATABASE_PATH:-rebusiness_automation.db}"

if [[ -f "$DB_PATH" ]]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo -e "${GREEN}✓ Database found (${DB_SIZE})${NC}"

    # Validate DB integrity
    if python3 -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); conn.execute('SELECT 1'); conn.close()" 2>/dev/null; then
        echo -e "${GREEN}✓ Database integrity OK${NC}"
    else
        echo -e "${RED}✗ Database corrupted or invalid${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Database not found at ${DB_PATH}${NC}"
    echo "Creating new database..."
    cd dashboard
    python3 init_db.py
    cd ..
    echo -e "${GREEN}✓ Database initialized${NC}"
fi

echo ""

# ============================================================================
# 5. Check Directories and Permissions
# ============================================================================
echo -e "${BLUE}[5/6]${NC} Checking directories and permissions..."

REQUIRED_DIRS=("dashboard" "dashboard/logs" "rfq_downloads" "ai_agents/ThomasNetAgent")

for dir in "${REQUIRED_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo -e "${GREEN}✓ ${dir}/${NC}"
    else
        echo -e "${YELLOW}⚠ Creating missing directory: ${dir}${NC}"
        mkdir -p "$dir"
    fi
done

# Create logs directory if missing
if [[ ! -d "dashboard/logs" ]]; then
    mkdir -p dashboard/logs
fi

# Check write permissions
if touch dashboard/logs/.test 2>/dev/null; then
    rm dashboard/logs/.test
    echo -e "${GREEN}✓ Write permissions OK${NC}"
else
    echo -e "${RED}✗ No write permissions to dashboard/logs${NC}"
    exit 1
fi

echo ""

# ============================================================================
# 6. Check Chrome/Chromium Installation
# ============================================================================
echo -e "${BLUE}[6/6]${NC} Checking Chrome/Chromium..."

if command -v chromium &> /dev/null; then
    CHROMIUM_VERSION=$(chromium --version)
    echo -e "${GREEN}✓ Chromium found: ${CHROMIUM_VERSION}${NC}"
elif command -v chromium-browser &> /dev/null; then
    CHROMIUM_VERSION=$(chromium-browser --version)
    echo -e "${GREEN}✓ Chromium found: ${CHROMIUM_VERSION}${NC}"
elif command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo -e "${GREEN}✓ Chrome found: ${CHROME_VERSION}${NC}"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ -d "/Applications/Google Chrome.app" ]] || [[ -d "/Applications/Chromium.app" ]]; then
        echo -e "${GREEN}✓ Chrome/Chromium found (macOS)${NC}"
    else
        echo -e "${YELLOW}⚠ Chrome not found in /Applications${NC}"
        WARNINGS+=("Install Chrome or Chromium for local testing")
    fi
else
    echo -e "${YELLOW}⚠ Chrome/Chromium not found${NC}"
    echo "Install with: sudo apt-get install chromium or download from https://www.google.com/chrome"
    WARNINGS+=("Chrome/Chromium required for automation")
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo "===================================="
echo -e "${GREEN}✓ Validation Complete${NC}"
echo ""

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo -e "${YELLOW}Warnings:${NC}"
    for warning in "${WARNINGS[@]}"; do
        echo "  ⚠ $warning"
    done
    echo ""
fi

# ============================================================================
# Export Configuration Variables
# ============================================================================
echo -e "${BLUE}Configuration Summary:${NC}"
echo "  Deployment Mode: ${DEPLOYMENT_MODE:-local}"
echo "  Database: ${DB_PATH}"
echo "  Max Vendors/RFQ: ${MAX_VENDORS_PER_RFQ:-5}"
echo "  Proxy Rotation: ${ENABLE_PROXY_ROTATION:-True}"
echo "  DataDome Strategy: ${DATADOME_STRATEGY:-adaptive}"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo ""

# ============================================================================
# Ready to Start
# ============================================================================
echo -e "${GREEN}✓ Dashboard is ready to run!${NC}"
echo ""
echo "Start the dashboard with:"
echo "  python3 dashboard/app.py"
echo ""
echo "Or use the launcher script:"
echo "  ./run_dashboard_full.sh"
echo ""

# Export env vars for parent shell
export PYTHONUNBUFFERED=1
export FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_APP="${FLASK_APP:-dashboard/app.py}"

exit 0
