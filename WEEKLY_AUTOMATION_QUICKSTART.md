# 🚀 Quick Start Guide - Weekly RFQ Automation

## Prerequisites Checklist

Before starting the automation, ensure:

- [x] Python 3.8+ installed
- [x] All dependencies installed (`pip install -r requirements.txt`)
- [x] Database is accessible (`rebusiness_automation.db`)
- [x] `.env` file configured with credentials
- [x] Chrome/Firefox browser available for ThomasNet

## Option 1: Start Full 7-Day Automation (Recommended)

```bash
cd /Users/apple/Downloads/rebusinessautomationproject

# Start automation in background
nohup python3 run_weekly_automation.py > weekly_automation.log 2>&1 &

# Save process ID for management
echo $! > automation.pid

# Check status immediately
python3 check_automation_status.py
```

**This will run for 7 days, checking for new RFQs every 3 hours.**

---

## Option 2: Test Mode (Recommended First!)

Test with a single cycle before running the full week:

```bash
# Test mode - runs one cycle then exits
python3 run_weekly_automation.py --test-mode
```

Expected output:
- ✅ Finds unprocessed RFQs
- ✅ Processes them with ThomasNet
- ✅ Creates status file
- ✅ Generates logs
- ✅ Exits cleanly

---

## Option 3: Custom Duration

Run for a shorter period (e.g., 1 day for testing):

```bash
# Run for 1 day, checking every hour
python3 run_weekly_automation.py --duration-days 1 --check-interval 60
```

---

## Monitoring

### Check Status Anytime

```bash
python3 check_automation_status.py
```

Shows:
- 🟢 Current status (RUNNING/STOPPED/COMPLETED)
- ⏰ Time elapsed and remaining
- 📊 Progress bar
- 📈 RFQs processed and vendors contacted
- ⚠️ Recent errors (if any)

### Continuous Monitoring (Live Updates)

```bash
# Watch mode - refreshes every 60 seconds
python3 check_automation_status.py --watch
```

### View Live Logs

```bash
# Follow the log in real-time
tail -f logs/weekly_automation/weekly_*.log
```

---

## Management Commands

### Stop Automation

```bash
# Find and stop the process
kill $(cat automation.pid)
```

### Resume After Stop

```bash
python3 run_weekly_automation.py --resume
```

### Start Fresh Run

```bash
# Remove old status and start new
rm automation_status.json
python3 run_weekly_automation.py
```

---

## What Happens During Automation?

Every 3 hours (by default), the automation:

1. **Checks for unprocessed RFQs** in `rfq_downloads/`
2. **Extracts product names** from each RFQ document
3. **Searches ThomasNet** for matching vendors
4. **Selects top 5 vendors** (configurable)
5. **Submits RFQ with attachment** to each vendor
6. **Tracks results** in `automation_status.json`
7. **Logs everything** to `logs/weekly_automation/`

Between cycles, it sleeps and waits for the next interval.

---

## Troubleshooting

### Automation Not Starting

Check logs:
```bash
tail -100 weekly_automation.log
```

Common issues:
- Database not accessible → Check `database_manager.py`
- Chrome not running → Start Chrome with debugging
- Missing dependencies → Run `pip install -r requirements.txt`

### Status Shows "NOT RUNNING"

The `automation_status.json` file doesn't exist. Either:
- Automation hasn't been started yet
- Process crashed (check logs)

### RFQs Not Being Processed

Check:
```bash
# See if there are unprocessed RFQs
ls -la rfq_downloads/2026-*/

# Check the processed log
cat thomasnet_processed.txt
```

### ThomasNet Submission Failing

Ensure:
- Chrome with remote debugging is running
- Logged into ThomasNet in that Chrome session
- Network connectivity is stable

---

## Expected Results (After 7 Days)

If running successfully for a full week:

- ✅ **50-100 RFQs** processed
- ✅ **250-500 vendors** contacted
- ✅ **Success rate** > 80%
- ✅ **Logs** properly organized in `logs/weekly_automation/`
- ✅ **Final summary** in `automation_weekly_summary_*.json`

---

## File Structure

```
rebusinessautomationproject/
├── run_weekly_automation.py          # Main automation wrapper
├── check_automation_status.py        # Status checker
├── automation_status.json            # Live status (created at runtime)
├── automation.pid                    # Process ID (created at runtime)
├── weekly_automation.log             # Main log (created at runtime)
├── logs/
│   └── weekly_automation/
│       └── weekly_*.log              # Detailed logs
├── rfq_downloads/                    # Generated RFQ files
│   └── 2026-02-*/
└── automation_weekly_summary_*.json  # Final report (created at end)
```

---

## Next Steps

1. **Test first**: `python3 run_weekly_automation.py --test-mode`
2. **Start automation**: `nohup python3 run_weekly_automation.py > weekly_automation.log 2>&1 &`
3. **Monitor daily**: `python3 check_automation_status.py`
4. **Review after 7 days**: Check final summary report

---

🎉 **You're all set! The automation will handle everything for the next 7 days.**
