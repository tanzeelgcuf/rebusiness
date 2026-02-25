# ThomasNet Automation - README

## Overview
Complete automation system for submitting RFQs to ThomasNet vendors.

## Features
- ✅ Automated vendor search and selection
- ✅ Intelligent vendor ranking (top 5 per product)
- ✅ RFQ form filling and submission
- ✅ Proxy support (Tor/residential proxies)
- ✅ Detailed logging and reporting
- ✅ Batch processing from CSV
- ✅ Production deployment ready

## Quick Start

### 1. Setup
```bash
# Run setup script
chmod +x deployment/setup.sh
./deployment/setup.sh

# Configure credentials
cp .env.example .env
# Edit .env with your ThomasNet credentials
```

### 2. Test Individual Components

**Test Search & Selection:**
```bash
python test_thomasnet_simple.py
```

**Test Form Filling:**
```bash
python test_rfq_form_filler.py
```

### 3. Run Complete Automation

**Dry Run (no actual submissions):**
```bash
python run_thomasnet_automation.py
```

**Live Run (real submissions):**
Edit `run_thomasnet_automation.py` and set `dry_run = False`

## Configuration

### Environment Variables (.env)
```bash
THOMASNET_EMAIL=your_email@example.com
THOMASNET_PASSWORD=your_password
THOMASNET_PROXY=  # Optional: socks5://127.0.0.1:9050 for Tor
```

### Proxy Setup

**Option 1: Free (Tor)**
```bash
# Install Tor
brew install tor

# Start Tor
brew services start tor

# Set in .env
THOMASNET_PROXY=socks5://127.0.0.1:9050
```

**Option 2: Residential Proxies ($1.50/GB)**
```bash
# Set in .env
THOMASNET_PROXY=http://username:password@proxy.provider.com:port
```

Cost: ~$26/month for 50 RFQs/day (see PROXY_COST_ANALYSIS.md)

## Batch Processing

Edit `products_input.csv` with your products:
```csv
product_name,rfq_summary,max_vendors
"CNC machining","Your RFQ text here...",5
```

Then run batch automation (coming soon).

## Production Deployment

### Scheduled Runs
```bash
# Install cron job
crontab deployment/crontab.txt

# Runs daily at 9 AM automatically
```

### Monitoring
- Logs: `logs/automation_*.log`
- Reports: `reports/report_*.json`

## Workflow

1. **Login** - Manual login to ThomasNet (one-time per session)
2. **Search** - Automated search for vendors
3. **Select** - Rank and select top 5 vendors
4. **Submit** - Fill and submit RFQ forms
5. **Report** - Generate JSON report with results

## Cost Analysis

For 50 RFQs/day (250 vendor submissions):
- **Bandwidth**: ~0.58 GB/day
- **Proxy Cost**: $0.87/day ($26/month)
- **Cost per RFQ**: $0.017 (less than 2 cents)

See `PROXY_COST_ANALYSIS.md` for details.

## Troubleshooting

**IP Blocked:**
- Enable proxy in .env
- Use Tor or residential proxies

**Captcha Issues:**
- Solve manually during login
- Session persists for multiple searches

**Form Filling Fails:**
- Check logs for selector errors
- ThomasNet may have changed their HTML
- Update selectors in form_filler.py

## Files

- `run_thomasnet_automation.py` - Main automation script
- `test_thomasnet_simple.py` - Test search & selection
- `test_rfq_form_filler.py` - Test form filling
- `products_input.csv` - Batch input template
- `deployment/setup.sh` - Setup script
- `deployment/crontab.txt` - Cron schedule

## Support

For issues or questions, check:
1. Logs in `logs/` directory
2. Implementation plan: `brain/*/implementation_plan.md`
3. Task tracker: `brain/*/task.md`
