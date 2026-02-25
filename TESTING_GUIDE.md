# Complete End-to-End Test Guide

## Overview

This guide will walk you through running a complete test of the entire automation system with live dashboard tracking.

## Setup (One-Time)

### 1. Start the Dashboard

```bash
cd dashboard
python3 app.py
```

Leave this running in a terminal. The dashboard will be available at: **http://localhost:5000**

### 2. Start Chrome with Remote Debugging

In another terminal:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

### 3. Sign In to ThomasNet

In the Chrome window that opened, go to https://www.thomasnet.com and sign in.

---

## Running the Test

Open **http://localhost:5000** in a separate browser window (not the debugging Chrome) so you can monitor the dashboard while the test runs.

### Option 1: Automated Complete Test

```bash
python3 test_complete_pipeline.py
```

This will:
1. Scrape a solicitation from sam.gov
2. Generate an RFQ (.docx)
3. Submit to ThomasNet vendors
4. Pause at each step so you can check the dashboard

**Dashboard Tracking:**
- After Step 1 → Check "Solicitations" page
- After Step 2 → Check "RFQs" page  
- After Step 3 → Check "Vendors" page
- Finally → Check "Home" for updated stats

### Option 2: Manual Step-by-Step

If you prefer more control:

#### Step 1: Generate RFQ
```bash
python3 main_workflow.py --keyword "industrial equipment" --pages 1
```

**Dashboard:** Go to `/solicitations` and `/rfqs` to see the new entries.

#### Step 2: Submit to ThomasNet
```bash
python3 run_complete_automation.py
```

**Dashboard:** Go to `/vendors` to see the submissions.

---

## What to Watch on Dashboard

### Home Page (`/`)
- **Statistics cards** will update with new counts
- **Recent activity** shows latest solicitations and vendors
- **Weekly growth** metrics update

### Solicitations (`/solicitations`)
- New entries appear as they're scraped
- Search by contract ID
- Click to view details

### RFQs (`/rfqs`)
- Generated RFQs appear here
- Download .docx files
- Regenerate if needed
- See quality scores

### Vendors (`/vendors`)
- All ThomasNet submissions tracked
- Switch between "Group by Vendor" and "Group by Product"
- See submission timestamps
- Success/failure status

### Automation (`/automation`)
- Live status (Running/Stopped)
- Recent logs
- Manual triggers (future feature)

---

## Expected Results

After running the complete test:

| Metric | Expected Value |
|--------|---------------|
| Solicitations | +10 (from 1 page search) |
| RFQs Generated | +1 |
| Vendor Submissions | +5 (5 vendors contacted) |
| Unique Vendors | +5 |

---

## Troubleshooting

### Dashboard not accessible
```bash
# Check if it's running
lsof -i :5000

# Restart if needed
cd dashboard && python3 app.py
```

### flask_cors error
```bash
pip install flask-cors
```

### Chrome debugging not connecting
```bash
# Kill existing Chrome instances
killall "Google Chrome"

# Restart with debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

### No RFQs generating
- Check API key in `config.py`
- Ensure solicitation has attachments
- Check `automation.log` for errors

---

## Continuous Operation

For 24/7 operation with dashboard tracking:

```bash
# Terminal 1: Dashboard
cd dashboard && python3 app.py

# Terminal 2: Automation (checks every 3 hours)
python3 run_complete_automation.py --continuous
```

Now you can access the dashboard anytime to see:
- Real-time statistics
- All generated RFQs
- Complete vendor submission history

---

**🎉 Enjoy your fully automated RFQ pipeline with live dashboard tracking!**
