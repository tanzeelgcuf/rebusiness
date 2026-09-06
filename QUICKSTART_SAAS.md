# Multi-Tenant SaaS RFQ Automation Platform - Quick Start Guide

**Version:** 1.0  
**Date:** 2026-09-06  
**Status:** Phase 1 Complete + Phase 2 Agent Adapters Ready

---

## Prerequisites

- Python 3.9+
- Redis server (for Celery job queue)
- SMTP credentials (Gmail, SendGrid, etc.)
- LLM API keys (Gemini, OpenAI, or Groq)
- Optional: PostgreSQL (for production; SQLite used in dev)

---

## 1. Installation

### Clone & Setup

```bash
# Navigate to project directory
cd rebusinessautomationproject

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install SaaS dependencies
pip install -r requirements-saas.txt

# Also install original pipeline dependencies (optional)
pip install -r requirements.txt
```

### Configure Environment

```bash
# Create .env file
cat > .env << EOF
# Flask
FLASK_ENV=development
SECRET_KEY=dev-secret-key-12345
JWT_SECRET_KEY=jwt-secret-key-12345

# Database
DATABASE_URL=sqlite:///rebusiness_automation_saas.db
# For production:
# DATABASE_URL=postgresql://user:password@localhost/rebusiness_saas

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM APIs
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
GROQ_API_KEY=your-groq-key

# Company Info
RFQ_COMPANY_NAME=CampSable LLC
RFQ_VENDOR_EMAIL=bobbysmitty078@gmail.com
RFQ_COMPANY_CONTACT=Bobby Smitty
RFQ_COMPANY_PHONE=+1 (720) 980-6080

# SMTP (for email submission)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SENDER_EMAIL=bobbysmitty078@gmail.com

# CAPTCHA Solving (optional)
CAPSOLVER_API_KEY=your-capsolver-key

# Feature Flags
FEATURE_THOMASNET_SUBMISSION=true
FEATURE_EMAIL_SUBMISSION=true
FEATURE_BATCH_PROCESSING=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
EOF

# Load environment variables
source .env
```

---

## 2. Start Services

### Terminal 1: Redis Server

```bash
# Start Redis (if not running as service)
redis-server

# Verify Redis is running
redis-cli ping
# Expected response: PONG
```

### Terminal 2: Flask Development Server

```bash
# Activate venv
source venv/bin/activate

# Create logs directory
mkdir -p logs

# Start Flask app
python run.py

# Output:
# * Running on http://0.0.0.0:5000
# * Debug mode: on
```

### Terminal 3: Celery Worker

```bash
# Activate venv (in a new terminal)
source venv/bin/activate

# Start Celery worker
python celery_worker.py

# Output:
# celery worker - Starting Celery worker
# [2026-09-06 19:42:00+00:00] celery - INFO - Worker connected to broker at redis://localhost:6379/0
```

---

## 3. API Quick Start

### 3.1 Register New Tenant & User

```bash
curl -X POST http://localhost:5000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "demo-company",
    "tenant_name": "Demo Company Inc",
    "email": "demo@example.com",
    "password": "SecurePassword123!",
    "full_name": "Demo User"
  }'

# Response (save the access_token):
{
  "tenant": {
    "id": 1,
    "slug": "demo-company",
    "name": "Demo Company Inc"
  },
  "user": {
    "id": 1,
    "email": "demo@example.com",
    "full_name": "Demo User",
    "role": "admin"
  },
  "tokens": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "Bearer"
  }
}
```

Store the `access_token` for subsequent requests.

### 3.2 Get Current User Info

```bash
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

curl -X GET http://localhost:5000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "tenant": {
    "id": 1,
    "slug": "demo-company",
    "name": "Demo Company Inc",
    "subscription_tier": "basic",
    "status": "active"
  },
  "user": {
    "id": 1,
    "email": "demo@example.com",
    "full_name": "Demo User",
    "role": "admin",
    "is_active": true,
    "created_at": "2026-09-06T19:42:00.000000",
    "last_login": "2026-09-06T19:42:05.000000"
  }
}
```

### 3.3 Start Automation Workflow 🚀

```bash
curl -X POST http://localhost:5000/api/v1/automation/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Response:
{
  "run_id": 1,
  "status": "queued",
  "created_at": "2026-09-06T19:42:10.000000",
  "message": "Automation workflow queued. Poll /automation/{run_id} for progress."
}
```

Save the `run_id` for polling progress.

### 3.4 Poll Automation Status

```bash
export RUN_ID="1"

# Poll every 2 seconds
while true; do
  curl -s -X GET http://localhost:5000/api/v1/automation/$RUN_ID \
    -H "Authorization: Bearer $TOKEN" | jq '.'
  
  sleep 2
done

# Sample response (in progress):
{
  "run_id": 1,
  "status": "running",
  "progress_percent": 40.0,
  "created_at": "2026-09-06T19:42:10.000000",
  "start_time": "2026-09-06T19:42:11.000000",
  "end_time": null,
  "duration_seconds": null,
  "results": {
    "solicitations_found": 5,
    "rfqs_generated": 3,
    "products_extracted": 0,
    "vendors_found": 0,
    "submissions_sent": 0
  },
  "agent_logs": [
    {
      "agent_name": "SamGovAgent",
      "step_number": 1,
      "status": "success",
      "attempt_number": 1,
      "retry_count_max": 2,
      "error_message": null,
      "start_time": "2026-09-06T19:42:11.000000",
      "end_time": "2026-09-06T19:42:45.000000",
      "duration_ms": 34000
    },
    {
      "agent_name": "AttachmentReaderAgent",
      "step_number": 2,
      "status": "running",
      "attempt_number": 1,
      "retry_count_max": 2,
      "error_message": null,
      "start_time": "2026-09-06T19:42:46.000000",
      "end_time": null,
      "duration_ms": null
    }
  ]
}

# Final response (completed):
{
  "run_id": 1,
  "status": "completed",
  "progress_percent": 100.0,
  "created_at": "2026-09-06T19:42:10.000000",
  "start_time": "2026-09-06T19:42:11.000000",
  "end_time": "2026-09-06T19:57:35.000000",
  "duration_seconds": 904,
  "results": {
    "solicitations_found": 5,
    "rfqs_generated": 5,
    "products_extracted": 12,
    "vendors_found": 47,
    "submissions_sent": 235
  },
  "error_message": null,
  "agent_logs": [
    ... (all 5 agents with success status)
  ]
}
```

### 3.5 Get Dashboard Stats

```bash
curl -X GET http://localhost:5000/api/v1/dashboard/stats \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "automations": {
    "total": 1,
    "completed": 1,
    "failed": 0,
    "success_rate_percent": 100.0
  },
  "rfqs": {
    "total": 5,
    "sent": 235
  },
  "vendors": {
    "total": 47,
    "with_email": 45
  },
  "solicitations": {
    "total": 5
  },
  "recent_activity": {
    "automations_7d": 1,
    "rfqs_7d": 5
  }
}
```

### 3.6 List RFQs

```bash
curl -X GET "http://localhost:5000/api/v1/rfqs?page=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "page": 1,
  "per_page": 10,
  "total": 5,
  "total_pages": 1,
  "rfqs": [
    {
      "rfq_id": 1,
      "contract_id": "SAM-2026-09-0001",
      "rfq_type": "PRODUCT",
      "format": "markdown",
      "generated_date": "2026-09-06T19:45:00.000000",
      "sent_to_vendor": true,
      "sent_date": "2026-09-06T19:55:00.000000",
      "vendor_email_recipient": "contact@vendor1.com",
      "content_length": 2847
    }
  ]
}
```

### 3.7 List Vendors

```bash
curl -X GET "http://localhost:5000/api/v1/vendors?page=1&limit=10&email_status=Ready" \
  -H "Authorization: Bearer $TOKEN"

# Response:
{
  "page": 1,
  "per_page": 10,
  "total": 45,
  "total_pages": 5,
  "vendors": [
    {
      "vendor_id": 1,
      "contract_id": "SAM-2026-09-0001",
      "name": "Industrial Supplies Corp",
      "website": "https://industrialsupplies.com",
      "email": "sales@industrialsupplies.com",
      "phone": "+1 (555) 123-4567",
      "location": "Chicago, IL",
      "confidence_score": 85,
      "email_status": "Ready",
      "created_at": "2026-09-06T19:50:00.000000"
    }
  ]
}
```

---

## 4. Monitoring & Debugging

### Check Flask Logs

```bash
tail -f logs/app.log

# Sample output:
2026-09-06 19:42:11 - app - INFO - Starting RFQ Automation SaaS Platform...
2026-09-06 19:42:11 - app - INFO - Environment: development
2026-09-06 19:42:11 - app - INFO - Debug: True
2026-09-06 19:42:15 - app.auth - INFO - New tenant and user created
2026-09-06 19:42:20 - app.orchestration - INFO - Workflow execution started
```

### Check Celery Worker Logs

```bash
# Monitor worker in real-time
# (already showing in the celery worker terminal)

# Sample output:
[2026-09-06 19:42:20] [celery] [INFO] Task automation.run_automation_workflow[abc123] received
[2026-09-06 19:42:21] [celery] [INFO] Task automation.run_automation_workflow[abc123] started running
[2026-09-06 19:57:35] [celery] [INFO] Task automation.run_automation_workflow[abc123] succeeded
```

### Database Inspection

```bash
# Connect to SQLite database
sqlite3 rebusiness_automation_saas.db

# List all tables
.tables

# Query tenants
SELECT id, slug, name, subscription_tier FROM tenants;

# Query automation runs
SELECT id, tenant_id, status, start_time, end_time FROM automation_runs;

# Query agent logs
SELECT agent_name, status, attempt_number, error_message 
FROM agent_loop_logs 
WHERE automation_run_id = 1;

# Exit
.quit
```

---

## 5. Subscription Tiers

### Switch to Different Tier

```bash
# Update via database
sqlite3 rebusiness_automation_saas.db \
  "UPDATE tenants SET subscription_tier = 'pro' WHERE id = 1;"

# Verify
sqlite3 rebusiness_automation_saas.db \
  "SELECT id, slug, subscription_tier FROM tenants WHERE id = 1;"

# Pro tier now has:
# - 3 retries per step (vs 2 for basic)
# - 100 automations/month (vs 10)
# - 50 vendors per RFQ (vs 10)
```

---

## 6. Common Issues & Troubleshooting

### Issue: "Redis connection refused"
```bash
# Solution: Make sure Redis is running
redis-cli ping
# If error, start Redis:
redis-server
```

### Issue: "JWT token expired"
```bash
# Solution: Refresh your token
curl -X POST http://localhost:5000/api/v1/auth/refresh \
  -H "Authorization: Bearer $REFRESH_TOKEN"
```

### Issue: "Tenant context not found"
```bash
# Solution: Make sure you're using the access_token in Authorization header
curl -X GET http://localhost:5000/api/v1/automation/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Issue: "Database is locked"
```bash
# Solution: SQLite can have locking issues; switch to PostgreSQL for production
# For dev, just restart the Flask server
```

### Issue: "Agent failed after X attempts"
```bash
# This is normal - agents retry automatically based on subscription tier
# Check logs for specific error:
tail -f logs/app.log | grep "error_message"
```

---

## 7. Testing Complete Workflow

### Automated Test Script

```bash
#!/bin/bash
# test_saas_workflow.sh

set -e

echo "🚀 Testing Multi-Tenant SaaS Platform"

# 1. Signup
echo "1️⃣ Registering new tenant..."
SIGNUP=$(curl -s -X POST http://localhost:5000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "test-'$RANDOM'",
    "tenant_name": "Test Company",
    "email": "test'$RANDOM'@example.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }')

TOKEN=$(echo $SIGNUP | jq -r '.tokens.access_token')
echo "✅ Registered. Token: ${TOKEN:0:20}..."

# 2. Get user info
echo "2️⃣ Fetching user info..."
curl -s -X GET http://localhost:5000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq '.user'
echo "✅ User info retrieved"

# 3. Start automation
echo "3️⃣ Starting automation workflow..."
START=$(curl -s -X POST http://localhost:5000/api/v1/automation/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')

RUN_ID=$(echo $START | jq -r '.run_id')
echo "✅ Automation started. Run ID: $RUN_ID"

# 4. Poll status
echo "4️⃣ Polling status (max 60 seconds)..."
for i in {1..30}; do
  STATUS=$(curl -s -X GET http://localhost:5000/api/v1/automation/$RUN_ID \
    -H "Authorization: Bearer $TOKEN" | jq '.status')
  
  echo "  [$i/30] Status: $STATUS"
  
  if [[ "$STATUS" == '"completed"' ]]; then
    echo "✅ Automation completed!"
    break
  fi
  
  sleep 2
done

# 5. Get results
echo "5️⃣ Fetching final results..."
RESULTS=$(curl -s -X GET http://localhost:5000/api/v1/automation/$RUN_ID \
  -H "Authorization: Bearer $TOKEN")

echo "$RESULTS" | jq '.results'

echo "✅ Test complete!"
```

```bash
# Run the test
chmod +x test_saas_workflow.sh
./test_saas_workflow.sh
```

---

## 8. Production Deployment

### Docker Setup (Optional)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements-saas.txt .
RUN pip install -r requirements-saas.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "run:app"]
```

```bash
# Build and run
docker build -t rfq-saas .
docker run -p 5000:5000 -e FLASK_ENV=production rfq-saas
```

### Environment Variables for Production

```bash
export FLASK_ENV=production
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
export JWT_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
export DATABASE_URL=postgresql://user:password@prod-db:5432/rebusiness_saas
export REDIS_URL=redis://prod-redis:6379/0
```

---

## Summary

**You now have:**
- ✅ Multi-tenant SaaS platform running locally
- ✅ 5-step automated RFQ workflow
- ✅ Real-time progress tracking
- ✅ Agent loop retry logic with exponential backoff
- ✅ 15+ REST API endpoints
- ✅ Celery background job queue
- ✅ Audit logging and compliance trail

**Next Steps:**
1. Build web dashboard UI (optional - API polling works for now)
2. Test with real SAM.gov solicitations
3. Integrate with actual ThomasNet scraping
4. Deploy to production
5. Monitor and scale

---

**Questions?** Check the logs or review SAAS_PHASE1_IMPLEMENTATION.md

Generated: 2026-09-06  
Support: For issues, check logs/app.log or contact the development team
