# Quick Start - ThomasNet with Auto-RFQ Attachment

## Simple Test (Auto-finds latest RFQ)

```bash
# Make sure Chrome is running with debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-debug"

# Sign in to ThomasNet, then run:
python3 test_thomasnet_auto_rfq.py
```

This automatically finds and uses the **latest RFQ file** from `rfq_downloads/`

---

## Manual Test (Specify RFQ file)

```bash
python3 test_thomasnet_with_attachment.py rfq_downloads/2026-01-22/YOUR_RFQ_FILE.docx
```

---

## Production Usage

```python
from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

# Your product data
product = {
    'product_name': 'industrial bolts',
    'quantity': '1000 units', 
    'due_date': 'March 15, 2026'
}

# Path to RFQ document (from sam.gov agent)
rfq_doc = "rfq_downloads/2026-01-22/abc123_RFQ_PRODUCT.docx"

# Run automation
agent = ThomasNetAgent()
result = agent.select_vendors_and_submit_rfq(
    product=product,
    limit=5,
    attachment_file_path=rfq_doc
)
```

---

## File Structure

```
rfq_downloads/
├── 2026-01-22/
│   ├── abc123_RFQ_PRODUCT.docx          ← Your RFQ files
│   ├── abc123_RFQ_PRODUCT_validation_report.txt
│   └── ...
└── 2026-01-20/
    └── ...
```

The automation automatically uploads the .docx file to ThomasNet! 🎉
