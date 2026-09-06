#!/bin/bash
# =============================================================================
# Multi-Tenant SaaS RFQ Automation Platform - Manual Integration Test Script
# =============================================================================
# Tests:
#   1. Multi-tenant signup & authentication
#   2. Data isolation between tenants
#   3. SAM.gov connection (with form credentials)
#   4. Automation workflow execution
#   5. Real-time progress tracking
#   6. Dashboard metrics
#   7. All 19 API endpoints (auth, automation, dashboard, RFQs, vendors, SAM.gov)
#
# Usage:
#   ./tests/test_saas_workflow.sh [BASE_URL]
#   ./tests/test_saas_workflow.sh http://localhost:5000
# =============================================================================

set -e

BASE_URL="${1:-http://localhost:5000}"
API_BASE="$BASE_URL/api/v1"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test results
declare -a FAILURES

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

assert_eq() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        log_success "$message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "$message"
        log_error "  Expected: $expected"
        log_error "  Got: $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES+=("$message")
    fi
}

assert_contains() {
    local needle="$1"
    local haystack="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if echo "$haystack" | grep -q "$needle"; then
        log_success "$message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "$message"
        log_error "  Expected to contain: $needle"
        log_error "  Got: $haystack"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES+=("$message")
    fi
}

api_call() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local token="$4"

    local headers=(-H "Content-Type: application/json")
    if [ -n "$token" ]; then
        headers+=(-H "Authorization: Bearer $token")
    fi

    if [ -n "$data" ]; then
        curl -s -X "$method" "$API_BASE$endpoint" \
            "${headers[@]}" \
            -d "$data"
    else
        curl -s -X "$method" "$API_BASE$endpoint" \
            "${headers[@]}"
    fi
}

extract_json() {
    python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('$1', ''))" 2>/dev/null
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

log_section "PRE-FLIGHT CHECKS"

# Check if server is up
if ! curl -s -f "$BASE_URL/api/v1/health" > /dev/null 2>&1; then
    log_error "Server not reachable at $BASE_URL"
    log_info "Start the server with: python run.py"
    exit 1
fi
log_success "Server is reachable"

# Check if jq is available
if ! command -v jq &> /dev/null; then
    log_warning "jq not installed - using Python for JSON parsing"
    USE_JQ=false
else
    USE_JQ=true
fi

# =============================================================================
# Test 1: Health Check
# =============================================================================

log_section "TEST 1: Health Check"

HEALTH=$(curl -s "$API_BASE/health")
assert_contains "healthy" "$HEALTH" "Health endpoint returns healthy"

# =============================================================================
# Test 2: Multi-Tenant Signup (3 tenants)
# =============================================================================

log_section "TEST 2: Multi-Tenant Signup"

TIMESTAMP=$(date +%s)

# Tenant A
TENANT_A_SLUG="tenant-a-$TIMESTAMP"
TENANT_A_EMAIL="admin-a-$TIMESTAMP@example.com"
log_info "Registering tenant A: $TENANT_A_SLUG"

SIGNUP_A=$(api_call POST /auth/signup "{
    \"tenant_slug\": \"$TENANT_A_SLUG\",
    \"tenant_name\": \"Tenant A Corp\",
    \"email\": \"$TENANT_A_EMAIL\",
    \"password\": \"SecurePass123!\",
    \"full_name\": \"Admin A\"
}")

TOKEN_A=$(echo "$SIGNUP_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tokens']['access_token'])" 2>/dev/null)
TENANT_A_ID=$(echo "$SIGNUP_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tenant']['id'])" 2>/dev/null)
USER_A_ID=$(echo "$SIGNUP_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['user']['id'])" 2>/dev/null)

assert_eq "1" "$([ -n "$TOKEN_A" ] && echo 1 || echo 0)" "Tenant A signup returns access token"
assert_eq "1" "$([ -n "$TENANT_A_ID" ] && echo 1 || echo 0)" "Tenant A gets an ID"
assert_eq "1" "$([ -n "$USER_A_ID" ] && echo 1 || echo 0)" "Tenant A user gets an ID"

# Tenant B
TENANT_B_SLUG="tenant-b-$TIMESTAMP"
TENANT_B_EMAIL="admin-b-$TIMESTAMP@example.com"
log_info "Registering tenant B: $TENANT_B_SLUG"

SIGNUP_B=$(api_call POST /auth/signup "{
    \"tenant_slug\": \"$TENANT_B_SLUG\",
    \"tenant_name\": \"Tenant B Corp\",
    \"email\": \"$TENANT_B_EMAIL\",
    \"password\": \"SecurePass123!\",
    \"full_name\": \"Admin B\"
}")

TOKEN_B=$(echo "$SIGNUP_B" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tokens']['access_token'])" 2>/dev/null)
TENANT_B_ID=$(echo "$SIGNUP_B" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tenant']['id'])" 2>/dev/null)

assert_eq "1" "$([ -n "$TOKEN_B" ] && echo 1 || echo 0)" "Tenant B signup returns access token"

# Verify different IDs (no collision)
if [ "$TENANT_A_ID" != "$TENANT_B_ID" ]; then
    log_success "Tenants have different IDs (no collision)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_error "Tenant ID collision detected!"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

# =============================================================================
# Test 3: Authentication Endpoints
# =============================================================================

log_section "TEST 3: Authentication"

# Login as tenant A
LOGIN_A=$(api_call POST /auth/login "{
    \"email\": \"$TENANT_A_EMAIL\",
    \"password\": \"SecurePass123!\"
}")
LOGIN_TOKEN=$(echo "$LOGIN_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tokens']['access_token'])" 2>/dev/null)
assert_eq "1" "$([ -n "$LOGIN_TOKEN" ] && echo 1 || echo 0)" "Login returns new access token"

# Login with wrong password (should fail)
BAD_LOGIN=$(api_call POST /auth/login "{
    \"email\": \"$TENANT_A_EMAIL\",
    \"password\": \"WrongPassword\"
}")
BAD_LOGIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$TENANT_A_EMAIL\", \"password\": \"WrongPassword\"}")
assert_eq "401" "$BAD_LOGIN_STATUS" "Wrong password returns 401"

# Get current user info
ME_A=$(api_call GET /auth/me "" "$TOKEN_A")
assert_contains "Tenant A" "$ME_A" "GET /auth/me returns tenant A info"

# Refresh token
REFRESH_A=$(api_call POST /auth/refresh "" "$(echo "$SIGNUP_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['tokens']['refresh_token'])" 2>/dev/null)")
REFRESH_TOKEN_NEW=$(echo "$REFRESH_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['access_token'])" 2>/dev/null)
assert_eq "1" "$([ -n "$REFRESH_TOKEN_NEW" ] && echo 1 || echo 0)" "Token refresh works"

# =============================================================================
# Test 4: Data Isolation (CRITICAL)
# =============================================================================

log_section "TEST 4: Data Isolation Between Tenants"

# Start automation as tenant A
START_A=$(api_call POST /automation/start "{}" "$TOKEN_A")
RUN_A_ID=$(echo "$START_A" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['run_id'])" 2>/dev/null)
assert_eq "1" "$([ -n "$RUN_A_ID" ] && echo 1 || echo 0)" "Tenant A can start automation"

# Start automation as tenant B
START_B=$(api_call POST /automation/start "{}" "$TOKEN_B")
RUN_B_ID=$(echo "$START_B" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['run_id'])" 2>/dev/null)
assert_eq "1" "$([ -n "$RUN_B_ID" ] && echo 1 || echo 0)" "Tenant B can start automation"

# Tenant A tries to access tenant B's run (should be 404 or 403)
CROSS_ACCESS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/automation/$RUN_B_ID" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "404" "$CROSS_ACCESS" "Cross-tenant access blocked (A → B)"

# Tenant B tries to access tenant A's run (should be 404 or 403)
CROSS_ACCESS_2=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/automation/$RUN_A_ID" \
    -H "Authorization: Bearer $TOKEN_B")
assert_eq "404" "$CROSS_ACCESS_2" "Cross-tenant access blocked (B → A)"

# =============================================================================
# Test 5: SAM.gov Connection
# =============================================================================

log_section "TEST 5: SAM.gov Integration"

# Get SAM.gov settings (should be disconnected)
SAM_SETTINGS=$(api_call GET /sam-gov/settings "" "$TOKEN_A")
assert_contains "false" "$SAM_SETTINGS" "Initial SAM.gov status: not connected"

# Connect with mock credentials (this will fail in real SAM.gov, but tests the form)
SAM_CONNECT=$(api_call POST /sam-gov/connect "{
    \"api_key\": \"MOCK_KEY_FOR_TESTING_32_CHARS_MIN\",
    \"entity_id\": \"ABC123DEF456\",
    \"test_connection\": false
}" "$TOKEN_A")

# Should succeed (test_connection=false skips actual API call)
SAM_CONNECT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/sam-gov/connect" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_A" \
    -d "{
        \"api_key\": \"MOCK_KEY_FOR_TESTING_32_CHARS_MIN\",
        \"entity_id\": \"ABC123DEF456\",
        \"test_connection\": false
    }")
# Note: 201 if new, 200 if updated - both are success
if [ "$SAM_CONNECT_STATUS" = "201" ] || [ "$SAM_CONNECT_STATUS" = "200" ]; then
    log_success "SAM.gov connect endpoint accepts valid input"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    log_error "SAM.gov connect failed with status $SAM_CONNECT_STATUS"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))

# Test validation: short API key
SAM_INVALID=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/sam-gov/connect" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_A" \
    -d "{\"api_key\": \"short\", \"entity_id\": \"ABC123DEF456\"}")
assert_eq "400" "$SAM_INVALID" "Short API key returns 400"

# Test validation: bad entity ID format
SAM_INVALID_2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/sam-gov/connect" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_A" \
    -d "{\"api_key\": \"MOCK_KEY_FOR_TESTING_32_CHARS_MIN\", \"entity_id\": \"bad\"}")
assert_eq "400" "$SAM_INVALID_2" "Invalid entity ID returns 400"

# Get updated settings (should now show connected)
SAM_SETTINGS_2=$(api_call GET /sam-gov/settings "" "$TOKEN_A")
assert_contains "true" "$SAM_SETTINGS_2" "SAM.gov shows connected after connect"

# Test endpoint (will fail with mock key, but tests the endpoint)
SAM_TEST=$(api_call POST /sam-gov/test "{}" "$TOKEN_A")
assert_contains "success" "$SAM_TEST" "SAM.gov test endpoint returns response"

# Update sync settings
SAM_UPDATE=$(api_call PATCH /sam-gov/settings "{
    \"auto_sync_enabled\": true,
    \"sync_interval_hours\": 12,
    \"naics_codes\": [\"334111\"]
}" "$TOKEN_A")
SAM_UPDATE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$API_BASE/sam-gov/settings" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_A" \
    -d "{\"auto_sync_enabled\": true, \"sync_interval_hours\": 12}")
assert_eq "200" "$SAM_UPDATE_STATUS" "SAM.gov settings update works"

# Get sync history
SAM_HISTORY=$(api_call GET /sam-gov/sync-history "" "$TOKEN_A")
SAM_HISTORY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/sam-gov/sync-history" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$SAM_HISTORY_STATUS" "SAM.gov sync history endpoint works"

# Disconnect
SAM_DISCONNECT=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/sam-gov/disconnect" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$SAM_DISCONNECT" "SAM.gov disconnect works"

# =============================================================================
# Test 6: Dashboard Endpoints
# =============================================================================

log_section "TEST 6: Dashboard Metrics"

DASHBOARD_STATS=$(api_call GET /dashboard/stats "" "$TOKEN_A")
DASHBOARD_STATS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/dashboard/stats" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$DASHBOARD_STATS_STATUS" "Dashboard stats endpoint works"
assert_contains "automations" "$DASHBOARD_STATS" "Stats include automations"

RECENT_RUNS=$(api_call GET /dashboard/recent-runs "" "$TOKEN_A")
RECENT_RUNS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/dashboard/recent-runs" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$RECENT_RUNS_STATUS" "Recent runs endpoint works"

# =============================================================================
# Test 7: Automation Polling
# =============================================================================

log_section "TEST 7: Automation Progress Tracking"

# Poll tenant A's automation
for i in 1 2 3; do
    STATUS_A=$(api_call GET /automation/$RUN_A_ID "" "$TOKEN_A")
    log_info "Poll $i: $STATUS_A" | head -c 200
    echo ""
    sleep 1
done

# Get logs
LOGS_A=$(api_call GET /automation/$RUN_A_ID/logs "" "$TOKEN_A")
LOGS_A_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/automation/$RUN_A_ID/logs" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$LOGS_A_STATUS" "Automation logs endpoint works"

# Get history
HISTORY_A=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/automation/history" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$HISTORY_A" "Automation history endpoint works"

# =============================================================================
# Test 8: RFQ and Vendor Endpoints
# =============================================================================

log_section "TEST 8: RFQ and Vendor Endpoints"

RFQS_LIST=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/rfqs" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$RFQS_LIST" "RFQs list endpoint works"

VENDORS_LIST=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/vendors" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$VENDORS_LIST" "Vendors list endpoint works"

# =============================================================================
# Test 9: Authentication Required
# =============================================================================

log_section "TEST 9: Authentication Required for Protected Endpoints"

NO_AUTH=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/automation/history")
assert_eq "401" "$NO_AUTH" "No auth returns 401"

NO_AUTH_STATS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/dashboard/stats")
assert_eq "401" "$NO_AUTH_STATS" "Stats without auth returns 401"

NO_AUTH_SAM=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_BASE/sam-gov/settings")
assert_eq "401" "$NO_AUTH_SAM" "SAM.gov settings without auth returns 401"

# =============================================================================
# Test 10: Logout
# =============================================================================

log_section "TEST 10: Logout"

LOGOUT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/auth/logout" \
    -H "Authorization: Bearer $TOKEN_A")
assert_eq "200" "$LOGOUT_STATUS" "Logout works"

# =============================================================================
# Summary
# =============================================================================

log_section "TEST SUMMARY"

echo ""
echo -e "Tests Run:    ${BLUE}$TESTS_RUN${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed Tests:${NC}"
    for failure in "${FAILURES[@]}"; do
        echo -e "  ${RED}✗${NC} $failure"
    done
    exit 1
else
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
fi
