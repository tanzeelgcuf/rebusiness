# ThomasNet Agent - Quick Start Guide

## Prerequisites

1. **Install Dependencies**
   ```bash
   cd /Users/apple/Downloads/rebusinessautomationproject
   pip install -r ai_agents/ThomasNetAgent/requirements.txt
   playwright install firefox
   ```

2. **Configure Environment**
   
   Ensure `.env` file has:
   ```
   THOMASNET_EMAIL=your_email@example.com
   THOMASNET_PASSWORD=your_password
   ```

3. **Verify Configuration**
   ```bash
   python test_thomasnet_config.py
   ```

## Running Tests

### Unit Tests (Automated)

```bash
# Test vendor selector logic
python test_thomasnet_vendor_selector.py

# Test RFQ parser
python test_thomasnet_parser.py

# Test configuration
python test_thomasnet_config.py
```

### Integration Tests (Manual Interaction Required)

```bash
# Test authentication (requires manual captcha solving)
python test_thomasnet_auth.py
# Press Enter when prompted, then solve captcha if it appears

# Test CLI search
cd ai_agents/ThomasNetAgent
python cli.py test-search "industrial fasteners" --headless false

# Test end-to-end dry run (no actual submission)
cd ../..
python test_thomasnet_e2e_dryrun.py
```

## Using the CLI

### Test Search
```bash
cd ai_agents/ThomasNetAgent
python cli.py test-search "CNC machining" --headless false
```

### Submit RFQ (Dry Run)
```bash
python cli.py submit \
  --rfq ../../4866eaf56f_RFQ.md \
  --dry-run \
  --headless false \
  --max-vendors 3
```

### Submit RFQ (Live - Actual Submission)
```bash
python cli.py submit \
  --rfq ../../4866eaf56f_RFQ.md \
  --headless false \
  --max-vendors 5
```

### Batch Process Multiple RFQs
```bash
python cli.py batch --directory ../../rfq_outputs/ --headless false
```

### View Statistics
```bash
python cli.py stats
```

## Configuration

Edit `ai_agents/ThomasNetAgent/config.yaml`:

```yaml
thomasnet:
  headless: true  # Set to false for debugging
  browser_type: "firefox"  # Options: chromium, firefox, webkit
  max_daily_submissions: 25
  delay_between_submissions: 10  # seconds

vendor_selection:
  max_vendors_per_product: 5
  min_rating: 3.0
  require_verification: false

company:
  name: "Your Company Name"
  contact_name: "Your Name"
  email: "your@email.com"
  phone: "+1-555-123-4567"
```

## Troubleshooting

### Authentication Issues

**Problem:** Login fails or captcha appears
- **Solution:** Run with `--headless false` to see what's happening
- Solve DataDome captcha manually when it appears
- Check that credentials in `.env` are correct

### Search Returns No Results

**Problem:** No vendors found
- **Solution:** Try different search terms
- Ensure you're logged in (authentication successful)
- Check ThomasNet website is accessible

### Parser Not Extracting Data

**Problem:** RFQ parser returns empty products
- **Solution:** Check RFQ file format
- Ensure file has clear product descriptions
- Look for "Notice ID", "Product Name", or CLIN tables

## Logs

Logs are saved to `logs/` directory:
- `thomasnet_automation.log` - Main application log
- `auth_success.png` - Screenshot after successful login
- `login_error.png` - Screenshot if login fails

## Next Steps

1. ✅ Run unit tests to verify setup
2. ⏳ Run authentication test (manual captcha)
3. ⏳ Test search functionality
4. ⏳ Run dry run with sample RFQ
5. 🎯 Submit actual RFQ when ready
