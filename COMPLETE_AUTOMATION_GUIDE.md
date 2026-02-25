# Complete Automation - Quick Start Guide

## Overview

This automation connects sam.gov RFQ generation → ThomasNet vendor submission in one complete pipeline.

## Modes

### 1. Process Existing RFQs (Default)
Finds all unprocessed RFQ files and submits them to ThomasNet:

```bash
python3 run_complete_automation.py
```

### 2. Continuous Monitoring
Checks for new RFQs every 3 hours and auto-submits:

```bash
python3 run_complete_automation.py --continuous
```

To check more frequently (e.g., every hour):
```bash
python3 run_complete_automation.py --continuous --interval 60
```

### 3. Generate & Submit
Generates new RFQs from sam.gov, then immediately submits to ThomasNet:

```bash
# Generate RFQs for a specific keyword
python3 run_complete_automation.py --generate-and-submit --keyword "industrial bolts"

# Or use batch rotation
python3 run_complete_automation.py --generate-and-submit
```

### 4. Single RFQ
Process one specific RFQ file:

```bash
python3 run_complete_automation.py --rfq rfq_downloads/2026-01-22/abc123_RFQ_PRODUCT.docx
```

## Prerequisites

1. **Chrome with Remote Debugging** (for ThomasNet):
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="/tmp/chrome-debug"
   ```

2. **Signed in to ThomasNet** in that Chrome window

## Workflow

```
sam.gov Search
      ↓
  RFQ Generation
      ↓
  .docx file saved
      ↓
Extract Product Name ← from .docx or database
      ↓
Search ThomasNet
      ↓
Select 5 Vendors
      ↓
Submit RFQ with Attachment
      ↓
   ✅ COMPLETE
```

## Options

```bash
--max-vendors N          # Vendors per product (default: 5)
--interval M             # Check interval for continuous mode (minutes, default: 180 = 3 hours)
--pages N                # Pages to scrape in generate mode (default: 10)
--keyword "text"         # Search keyword for sam.gov
```

## Examples

```bash
# Process all pending RFQs right now
python3 run_complete_automation.py

# Run 24/7 automation checking every 3 hours (default)
python3 run_complete_automation.py --continuous

# Check more frequently (every hour)
python3 run_complete_automation.py --continuous --interval 60

# Generate 20 pages of "fasteners" RFQs and submit
python3 run_complete_automation.py --generate-and-submit \
  --keyword "fasteners" \
  --pages 20 \
  --max-vendors 10
```

## Tracking

The script creates `thomasnet_processed.txt` to track which RFQs have been submitted (prevents duplicates).

## Production Deployment

For 24/7 operation, run in continuous mode:

```bash
# Default: Check every 3 hours (aligns with main workflow)
nohup python3 run_complete_automation.py --continuous > automation.log 2>&1 &

# Or customize interval (e.g., every hour)
nohup python3 run_complete_automation.py --continuous --interval 60 > automation.log 2>&1 &
```

This will:
- Run in background
- Check every 3 hours (or custom interval)
- Log to automation.log
- Automatically recover from errors

---

🎉 **Complete automation achieved!**
