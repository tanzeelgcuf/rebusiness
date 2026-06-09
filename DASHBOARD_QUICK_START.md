# ThomasNet RFQ Dashboard - Quick Start Guide

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+
- Google Chrome or Chromium browser
- Internet connection
- ThomasNet account credentials

### Step 1: Configure Environment

```bash
# Copy the template and fill in your credentials
cp .env.dashboard.example .env.dashboard
nano .env.dashboard
```

**Required fields:**
- `THOMASNET_EMAIL` - Your ThomasNet login email
- `THOMASNET_PASSWORD` - Your ThomasNet login password
- `CAPSOLVER_API_KEY` - Get from https://www.capsolver.com (free tier available)
- `TWO_CAPTCHA_API_KEY` - Get from https://2captcha.com (fallback)

### Step 2: Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### Step 3: Initialize Database

```bash
cd dashboard
python3 init_db.py
cd ..
```

### Step 4: Run Pre-Flight Checks

```bash
python3 verify_dashboard.py
```

This verifies:
- ✓ Python environment
- ✓ Dependencies installed
- ✓ Configuration valid
- ✓ Database connected
- ✓ Proxy manager working
- ✓ API endpoints responding

---

## 🎯 Running the Dashboard

### Local Development (with Chrome GUI)

```bash
./run_dashboard_full.sh
```

This will:
1. Run pre-flight validation
2. Auto-detect deployment mode (local)
3. Start Chrome with debugging on port 9222
4. Launch Flask dashboard on http://localhost:5000

**Manual Chrome Launch** (if auto-launch fails):
```bash
# macOS
open -a "Google Chrome" --args --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222 &

# Then run dashboard
python3 dashboard/app.py
```

### Server Deployment (headless)

```bash
# Set deployment mode
export DEPLOYMENT_MODE=server

# Run launcher
./run_dashboard_full.sh
```

This runs Chrome in headless mode (no GUI) suitable for cloud servers.

---

## 💡 Usage Workflow

### 1. Upload Solicitation RFQs

Navigate to **Dashboard → RFQs** and upload your generated RFQ .docx files.

### 2. Monitor Solicitations

View all solicitations in **Dashboard → Solicitations**. Filter by status, date, or search.

### 3. Trigger ThomasNet Automation

Go to **Dashboard → Automation** and click **"Submit to Vendors"**.

**Options:**
- `Max Vendors`: Number of vendors per RFQ (default: 5)
- `Enable Proxy Rotation`: Rotate IP between submissions (enabled by default)

### 4. Real-Time Monitoring

- Watch submission progress in real-time
- View proxy pool health: `/api/proxy-status`
- Check browser connection: `/api/browser-status`
- Monitor logs: `tail -f dashboard/logs/submission.log`

---

## 🛡️ IP Blocking Prevention Features

### Proxy Rotation
- **Per-Vendor IP Rotation**: New IP for each vendor submission
- **Multi-Source**: Proxies from Proxifly + ProxyScrape (free)
- **Health Monitoring**: Auto-refill pool if below 10 working proxies
- **Failure Tracking**: Failed proxies cooldown for 10 minutes

### DataDome Bypass (Adaptive Strategy)
1. **Detect**: Check for DataDome slider on page
2. **Solve**: Use CapSolver (primary) or 2Captcha (fallback)
3. **Retry**: Get new proxy and retry (max 3 attempts)
4. **Pause**: Wait 5 seconds to avoid hard ban
5. **Skip**: Move to next vendor, return after 30 minutes

### Rate Limiting
- 3-5 second delay between vendor submissions
- Random jitter (±1 second) to avoid pattern detection
- Configurable in `.env.dashboard`

---

## 📊 Monitoring & Logging

### View Logs

```bash
# Real-time submission logs
tail -f dashboard/logs/submission.log

# Check proxy pool status
curl http://localhost:5000/api/proxy-status | jq

# Check browser status
curl http://localhost:5000/api/browser-status | jq
```

### Log Entries Include
- Timestamp of each submission
- Vendor name contacted
- Proxy IP used
- DataDome detection/bypass status
- Success/failure status
- Attachment upload confirmation

---

## ⚙️ Configuration

### Environment Variables (.env.dashboard)

```bash
# Proxy Settings
ENABLE_PROXY_ROTATION=True
MIN_PROXY_POOL_SIZE=10
PROXY_FAILURE_COOLDOWN=600

# DataDome Strategy
DATADOME_STRATEGY=adaptive  # Options: adaptive, retry_only, pause_and_retry
DATADOME_MAX_RETRIES=3
DATADOME_WAIT_TIME=5

# Rate Limiting
SUBMISSION_DELAY_MIN=3
SUBMISSION_DELAY_MAX=5

# Deployment
DEPLOYMENT_MODE=local  # Options: local, server
FLASK_DEBUG=True
```

### Configuration File (config/deployment.yaml)

Full configuration with advanced options:
- Parallel submission settings
- Session rotation intervals
- Chrome profile management
- Database backup settings
- Monitoring & alerting thresholds

---

## 🧪 Testing

### Test Proxy Manager

```bash
python3 dashboard/utils/advanced_proxy_manager.py
```

Output shows:
- Available proxies from each source
- Proxy validation results
- Pool health statistics
- Proxy rotation in action

### Test Database

```bash
python3 -c "from database_manager import DatabaseManager; db = DatabaseManager(); print(f'Solicitations: {db.get_solicitations_count()}'); print(f'RFQs: {db.get_rfqs_count()}')"
```

### Test API Endpoints

```bash
# Get proxy status
curl http://localhost:5000/api/proxy-status

# Get automation status
curl http://localhost:5000/api/automation/status

# Get browser status
curl http://localhost:5000/api/browser-status
```

---

## 🐛 Troubleshooting

### Issue: "Chrome not found"
**Solution:** Install Chrome or Chromium, or manually start with:
```bash
google-chrome --remote-debugging-port=9222
```

### Issue: "No working proxies found"
**Solution:** Check internet connection, proxy sources may be temporarily unavailable. Proxies auto-refresh every 5 minutes.

### Issue: "DataDome block not solved"
**Solution:** 
1. Verify CapSolver/2Captcha API keys are valid
2. Check account has enough credits
3. Try manual solve by waiting 30 seconds before retry

### Issue: "Form submission failed"
**Solution:**
1. Check RFQ file is valid .docx
2. Verify attachment file path is accessible
3. Check vendor name matches ThomasNet search results
4. Review browser logs: `tail -f dashboard/logs/submission.log`

### Issue: "Authentication failed"
**Solution:**
1. Save new ThomasNet session:
   ```bash
   python3 save_thomasnet_session.py
   ```
2. This updates `dashboard/auth_state.json` with fresh cookies

---

## 📈 Performance Tips

- **Increase Max Vendors**: Higher `MAX_VENDORS_PER_RFQ` = more contacts but slower
- **Reduce Delays**: Lower `SUBMISSION_DELAY_MIN/MAX` (minimum 2-3 seconds recommended)
- **Multiple Sessions**: Deploy multiple instances with different IPs for scaling
- **Residential Proxies**: Consider paid proxies (IPRoyal, Bright Data) for reliability

---

## 🔐 Security & Compliance

- ✓ Credentials stored in local `.env.dashboard` (never committed)
- ✓ Session cookies saved locally in `dashboard/auth_state.json`
- ✓ HTTPS to ThomasNet enforced
- ✓ Rate limiting prevents abuse
- ✓ Audit logs created at `dashboard/logs/audit.log`

---

## 📞 Support

For issues or questions:
1. Check logs: `tail -f dashboard/logs/submission.log`
2. Run verification: `python3 verify_dashboard.py`
3. Check configuration: `cat .env.dashboard | grep -v "^#"`
4. Review deployment config: `cat config/deployment.yaml`
