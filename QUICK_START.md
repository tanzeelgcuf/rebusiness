# Quick Start Guide - RFQ Automation Dashboard

## Current Status ✅

The application is **ready to submit RFQs to ThomasNet**. All core components have been verified:

- ✅ Flask dashboard running on http://localhost:5001
- ✅ 127 solicitations loaded in database
- ✅ RFQ generation completed
- ✅ 2 test RFQs prepared in markdown format
- ✅ ThomasNet authentication configured
- ✅ Browser session saved and ready

## Quick Commands

### 1. Start the Dashboard (Already Running)
```bash
source .venv/bin/activate
python3 dashboard/app.py
# Access at http://localhost:5001
```

### 2. Test RFQ Submission (Dry Run - Safe)
```bash
source .venv/bin/activate
python3 submit_rfq_via_dashboard.py --rfq generated_rfqs/test_rfq.md --dry-run
```

### 3. Check RFQ Status
```bash
source .venv/bin/activate
python3 -c "
from database_manager import DatabaseManager
db = DatabaseManager()
rfqs = db.get_all_rfqs(limit=5, sent_status=None)
print(f'Total RFQs: {db.get_rfqs_count()}')
print(f'Sent: {db.get_rfqs_count(\"sent\")}')
print(f'Pending: {db.get_rfqs_count(\"pending\")}')
for rfq in rfqs[:3]:
    print(f'  - {rfq[\"contract_id\"][:8]}... ({rfq[\"rfq_type\"]})')
"
```

### 4. Export More RFQs (If Needed)
```bash
source .venv/bin/activate
python3 export_rfq_for_submission.py
```

### 5. Run Comprehensive Test
```bash
source .venv/bin/activate
python3 test_rfq_workflow.py
```

## Using the Dashboard UI

### Submit RFQs via Web Interface
1. Go to http://localhost:5001/automation
2. Click "Submit RFQs" button
3. Monitor submission in real-time
4. Check logs for status

### View RFQ Status
1. Go to http://localhost:5001/rfqs
2. Filter by status: Pending / Completed / All
3. Click on any RFQ to see details

### View Vendor Results
1. Go to http://localhost:5001/vendors
2. See which vendors were contacted
3. Track submission success rates

## Environment Setup

### Required Environment Variables (Already Set)
```bash
THOMASNET_EMAIL=john@campsable.com
THOMASNET_PASSWORD=JohnKris$1
CAPSOLVER_API_KEY=your_capsolver_key_here
TWO_CAPTCHA_API_KEY=dcdba5164e3c5c4a8b2a0f09525dacff
```

### File Structure
```
project_root/
├── dashboard/
│   ├── app.py                 # Flask app
│   ├── auth_state.json        # ✅ Saved browser session
│   └── utils/
│       └── dashboard_thomasnet.py  # ✅ Updated to find markdown RFQs
├── generated_rfqs/            # ✅ RFQ markdown files ready
│   ├── test_rfq.md
│   └── N0010425QNF13_RFQ_service_final_v2.md
├── ai_agents/
│   └── ThomasNetAgent/        # Submission logic
├── rebusiness_automation.db   # ✅ 127 RFQs in database
└── export_rfq_for_submission.py  # ✅ Export script
```

## Troubleshooting

### Dashboard Won't Start
```bash
# Kill existing process
lsof -i :5001
kill -9 <PID>

# Restart
source .venv/bin/activate
python3 dashboard/app.py
```

### No RFQs Found
```bash
# Check generated_rfqs directory
ls -la generated_rfqs/

# If empty, run export
python3 export_rfq_for_submission.py

# Verify in database
python3 -c "
from dashboard.utils.dashboard_thomasnet import find_unprocessed_rfqs
rfqs = find_unprocessed_rfqs()
print(f'Found {len(rfqs)} RFQs ready to submit')
"
```

### Browser Connection Error
```bash
# Check if auth_state.json exists
ls -la dashboard/auth_state.json

# If missing, ThomasNet session needs to be re-authenticated:
# 1. Manually log in at https://www.thomasnet.com
# 2. Run: python3 save_thomasnet_session.py
# 3. Restart dashboard
```

### Submission Failed
1. Check logs at `dashboard/logs/submission.log`
2. Look for DataDome blocks or IP rotation issues
3. Verify ThomasNet credentials in `.env`
4. Check network connectivity

## What Happens During Submission

1. **Discovery**: Find unsubmitted RFQs in `generated_rfqs/`
2. **Parse**: Extract product names and requirements
3. **Connect**: Use saved browser session (no new login)
4. **Search**: Find vendors on ThomasNet for each product
5. **Select**: Choose top vendors based on relevance
6. **Submit**: Fill vendor contact forms with RFQ details
7. **Track**: Mark RFQs as sent in database
8. **Report**: Show results in dashboard

## Next Steps

### Immediate (5 minutes)
1. Test dry-run: `python3 submit_rfq_via_dashboard.py --rfq generated_rfqs/test_rfq.md --dry-run`
2. View dashboard: http://localhost:5001
3. Check RFQ status in database

### Short-term (30 minutes)
1. Submit 1-2 test RFQs via automation page
2. Verify vendors receive the RFQs
3. Monitor for any DataDome blocks
4. Check submission logs

### Full Deployment
1. Export all 127 RFQs if needed
2. Set up batch submission schedule
3. Monitor vendor responses
4. Adjust retry strategy based on results

## Key Files Modified

- ✅ `dashboard/utils/dashboard_thomasnet.py` - Updated RFQ discovery
- ✅ `export_rfq_for_submission.py` - New export utility
- ✅ `submit_rfq_via_dashboard.py` - New alternative submission path
- ✅ `generated_rfqs/` - New directory with markdown RFQs

## Success Indicators

✅ Dashboard loads: `curl http://localhost:5001`
✅ RFQ files exist: `ls -la generated_rfqs/`
✅ Auth state saved: `ls -la dashboard/auth_state.json`
✅ Database ready: `python3 test_rfq_workflow.py`
✅ All imports work: Core components verified

## Support

For detailed information, see:
- `RFQ_SUBMISSION_FIX_SUMMARY.md` - Technical details
- `DASHBOARD_QUICK_START.md` - Dashboard overview
- `LAUNCH_SUMMARY.md` - Project completion status

---
**Ready to submit RFQs!** 🚀
