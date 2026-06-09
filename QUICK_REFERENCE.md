# 🚀 Quick Reference Card

## START HERE (3 commands)

```bash
# 1. Configure credentials (2 minutes)
nano .env.dashboard
# Fill: THOMASNET_EMAIL, THOMASNET_PASSWORD, API keys

# 2. Verify setup (1 minute)
python3 verify_dashboard.py

# 3. Run dashboard (immediate)
./run_dashboard_full.sh
```

**Dashboard URL:** http://localhost:5000

---

## Key Commands

| Task | Command |
|------|---------|
| Start dashboard | `./run_dashboard_full.sh` |
| Watch logs | `tail -f dashboard/logs/submission.log` |
| Check proxy pool | `curl http://localhost:5000/api/proxy-status \| jq` |
| Verify setup | `python3 verify_dashboard.py` |
| Edit config | `nano .env.dashboard` |
| View API docs | `curl http://localhost:5000/api` |

---

## Configuration Quick Ref

```bash
# Required (.env.dashboard)
THOMASNET_EMAIL=your-email@example.com
THOMASNET_PASSWORD=your-password
CAPSOLVER_API_KEY=get from https://www.capsolver.com
TWO_CAPTCHA_API_KEY=get from https://2captcha.com

# Optional (defaults work fine)
ENABLE_PROXY_ROTATION=True
DATADOME_STRATEGY=adaptive
SUBMISSION_DELAY_MIN=3
SUBMISSION_DELAY_MAX=5
DEPLOYMENT_MODE=local
```

---

## API Endpoints

```bash
# Get proxy pool status
curl http://localhost:5000/api/proxy-status

# Get browser connection status
curl http://localhost:5000/api/browser-status

# Get automation status
curl http://localhost:5000/api/automation/status

# Trigger RFQ submission
curl -X POST http://localhost:5000/api/automation/submit-rfqs \
  -H "Content-Type: application/json" \
  -d '{"max_vendors": 5}'
```

---

## File Locations

| File | Purpose |
|------|---------|
| `.env.dashboard` | Configuration (EDIT THIS) |
| `dashboard/logs/submission.log` | Real-time logs (WATCH THIS) |
| `dashboard/auth_state.json` | Browser session (auto-saved) |
| `config/deployment.yaml` | Full config reference |
| `rebusiness_automation.db` | Database (RFQs, vendors) |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Chrome not found" | Start manually: `google-chrome --remote-debugging-port=9222` |
| "No proxies" | Check internet, sources auto-refresh every 5 min |
| "DataDome block" | Verify API keys have credits, wait 30s, try again |
| "Form submission failed" | Check RFQ file is valid .docx, vendor name matches |
| "Port 5000 in use" | Kill: `lsof -i :5000 \| kill -9` |

---

## Monitoring

```bash
# Watch real-time submissions
watch -n 1 'tail -20 dashboard/logs/submission.log'

# Count successful submissions
grep "Successfully submitted" dashboard/logs/submission.log | wc -l

# See all DataDome blocks
grep "DataDome" dashboard/logs/submission.log

# Check proxy usage
grep "Using proxy:" dashboard/logs/submission.log | tail -10
```

---

## Features at a Glance

✅ Dashboard on http://localhost:5000  
✅ Auto-submit RFQs to ThomasNet vendors  
✅ Automatic attachment upload (.docx)  
✅ Per-vendor IP rotation (prevents blocks)  
✅ DataDome auto-bypass (CapSolver + 2Captcha)  
✅ Rate limiting (random 3-5s delays)  
✅ Real-time logging with timestamps  
✅ Headless mode (cloud deployment ready)  

---

## Success Indicators

- ✅ `./run_dashboard_full.sh` starts without errors
- ✅ Dashboard loads at http://localhost:5000
- ✅ `/api/proxy-status` shows active proxies
- ✅ Logs show "✓ Successfully submitted to [vendor]"
- ✅ Vendors receive RFQs with attachments
- ✅ No repeated IP blocks after 10+ submissions

---

## Production Deployment

```bash
# Server mode (headless, no Chrome GUI needed)
export DEPLOYMENT_MODE=server
./run_dashboard_full.sh

# Or with environment variables
DEPLOYMENT_MODE=server \
THOMASNET_EMAIL=your-email@example.com \
THOMASNET_PASSWORD=your-password \
CAPSOLVER_API_KEY=your-key \
./run_dashboard_full.sh
```

---

## Documentation Files

- **DASHBOARD_QUICK_START.md** - Full user guide
- **DELIVERY_SUMMARY.md** - Complete technical summary
- **IMPLEMENTATION_COMPLETE.md** - Architecture details
- **config/deployment.yaml** - Configuration reference
- **setup_dashboard.sh** - Pre-flight checks

---

## Need Help?

1. Run verification: `python3 verify_dashboard.py`
2. Check logs: `tail -f dashboard/logs/submission.log`
3. Check config: `grep -v "^#" .env.dashboard`
4. Test proxy: `python3 dashboard/utils/advanced_proxy_manager.py`
5. Read docs: `cat DASHBOARD_QUICK_START.md`

---

**You're all set!** Start with: `./run_dashboard_full.sh`
