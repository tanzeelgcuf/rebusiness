# Dashboard Manual Triggers - Setup & Usage Guide

## 🎯 Key Improvement: Browser-Based Automation

The dashboard now connects to your **logged-in Chrome browser** to avoid IP blocking!

---

## ⚙️ One-Time Setup

### Step 1: Start Chrome with Remote Debugging

Open Terminal and run:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

**Important:**
- This starts Chrome with debugging enabled on port 9222
- Keep this Chrome window open while using the dashboard
- You can minimize it, but don't close it

### Step 2: Log In to ThomasNet

In the Chrome window you just opened:
1. Go to https://www.thomasnet.com
2. Log in with your credentials
3. Leave the tab open

### Step 3: Start the Dashboard

In a new Terminal window:

```bash
cd /Users/apple/Downloads/rebusinessautomationproject/dashboard
python3 app.py
```

Dashboard will be available at: **http://localhost:5001**

---

## 🚀 Using the Dashboard

### Navigate to Automation Page

Open: **http://localhost:5001/automation**

---

### Generate RFQs Button

**What it does**: Scrapes SAM.gov and generates RFQ documents

**Steps:**
1. Enter a search keyword (e.g., "industrial equipment")
2. Choose number of pages to scrape (1-10)
3. Click **"Generate New RFQs"**

**What happens:**
- ⏳ Button shows "Generating..."
- ✅ Success message appears when started
- 📝 Logs update in real-time
- 📂 Check `/solicitations` and `/rfqs` pages for results

**Behind the scenes**: Runs `main_workflow.py` in background thread

---

### Submit to ThomasNet Button

**What it does**: Submits pending RFQs to vendors using your logged-in browser

**Prerequisites** (must be met):
- ✓ Chrome running with `--remote-debugging-port=9222`
- ✓ Logged in to ThomasNet in that Chrome
- ✓ Browser window stays open

**Steps:**
1. Ensure prerequisites are met (check yellow box on page)
2. Click **"Submit Pending RFQs"**
3. Confirm in the dialog

**What happens:**
- ⏳ Button shows "Submitting..."
- 🌐 You'll see browser tabs being controlled automatically
- ✅ Success message appears
- 📊 Check `/vendors` page for submission results

**Behind the scenes**: 
- Connects to your Chrome via CDP (Chrome DevTools Protocol)
- Reuses your logged-in ThomasNet session
- No IP blocking! ✨

---

## 🔍 Monitoring

### Real-Time Logs

The logs section at the bottom of the automation page:
- Auto-refreshes every 10 seconds
- Shows progress from both buttons
- Click "Refresh Logs" for manual update

### Status Indicators

- 🟢 **Green** = Automation is running
- ⚪ **Gray** = Stopped
- Loading states on buttons prevent double-clicks

---

## 🧪 Testing

### Test Browser Connection

Before using the Submit button, verify Chrome connection:

```bash
cd /Users/apple/Downloads/rebusinessautomationproject/dashboard/utils
python3 browser_connector.py
```

**Expected output:**
```
✅ SUCCESS!
   - Connected to browser
   - Current URL: https://www.thomasnet.com
   - ThomasNet login validated
```

### Test Single RFQ Submission

Test with one RFQ only:

```bash
cd /Users/apple/Downloads/rebusinessautomationproject/dashboard/utils
python3 dashboard_thomasnet.py --test-one
```

This will process one pending RFQ to verify everything works.

---

## 🎬 Complete Workflow Example

### End-to-End Test

1. **Setup** (one-time):
   ```bash
   # Terminal 1: Start Chrome with debugging
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="/tmp/chrome-debug"
   
   # Log in to ThomasNet in that Chrome
   
   # Terminal 2: Start dashboard
   cd /Users/apple/Downloads/rebusinessautomationproject/dashboard
   python3 app.py
   ```

2. **Generate RFQs**:
   - Open http://localhost:5001/automation
   - Keyword: "medical supplies"
   - Pages: 2
   - Click "Generate New RFQs"
   - Wait for success message

3. **View Results**:
   - Navigate to `/solicitations` - see new entries
   - Navigate to `/rfqs` - see generated documents
   - Download any .docx file to review

4. **Submit to ThomasNet**:
   - Return to `/automation`
   - Click "Submit Pending RFQs"
   - Confirm in dialog
   - Watch browser automation in Chrome window
   - Check `/vendors` for submission results

---

## ⚠️ Troubleshooting

### "Cannot connect to Chrome" Error

**Problem**: Dashboard can't connect to Chrome

**Solution**:
1. Check if Chrome is running with debugging:
   ```bash
   curl http://localhost:9222/json/version
   ```
   Should return JSON with Chrome version

2. If not working, restart Chrome with the debugging command

### "Not logged in to ThomasNet" Error

**Problem**: Browser connection works but ThomasNet login not detected

**Solution**:
1. Open Chrome (the debugging one)
2. Go to https://www.thomasnet.com
3. Log in manually
4. Verify you see your account menu
5. Try submission again

### Submissions Still Getting Blocked

**Problem**: Even with browser connection, getting blocked

**Solution**:
- Ensure you're using the SAME Chrome window (debugging one)
- Don't open ThomasNet in regular Chrome, use debugging Chrome
- Check that you see the browser tabs being controlled during submission

### Button Stuck in "Loading" State

**Problem**: Button shows "Generating..." or "Submitting..." forever

**Solution**:
1. Refresh the page
2. Check logs section for errors
3. Check Terminal where dashboard is running for error messages

---

## 📋 Quick Reference

### Chrome Debugging Setup
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"
```

### Start Dashboard
```bash
cd /Users/apple/Downloads/rebusinessautomationproject/dashboard
python3 app.py
```

### Test Connection
```bash
python3 dashboard/utils/browser_connector.py
```

### Dashboard URL
http://localhost:5001/automation

---

## ✅ Success Checklist

Before using Submit button:
- [ ] Chrome started with `--remote-debugging-port=9222`
- [ ] Logged in to ThomasNet in that Chrome
- [ ] Browser connection test passes
- [ ] Dashboard is running
- [ ] At least one RFQ exists to submit

---

**Ready to use!** 🎉

For questions or issues, check the logs at `/automation` page or Terminal output.
