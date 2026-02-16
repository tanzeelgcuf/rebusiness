# RFQ Management Dashboard

Web-based dashboard for managing solicitations, RFQs, and ThomasNet vendor submissions.

## Features

- 📊 **Dashboard Home** - Overview statistics and recent activity
- 📋 **Solicitations** - View all scraped solicitations with search
- 📄 **RFQ Management** - View, download, edit, and regenerate RFQs
- 🏢 **Vendor Tracking** - Track all ThomasNet vendor submissions
- ⚙️ **Automation Control** - Monitor and control automation status

## Quick Start

1. **Initialize Database**:
   ```bash
   cd dashboard
   python3 init_db.py
   ```

2. **Start Dashboard**:
   ```bash
   python3 app.py
   ```

3. **Access Dashboard**:
   Open http://localhost:5000 in your browser

## API Endpoints

### Solicitations
- `GET /api/solicitations` - List all solicitations
- `GET /api/solicitations/<id>` - Get solicitation details
- `GET /api/solicitations/stats` - Get statistics

### RFQs
- `GET /api/rfqs` - List all RFQs
- `GET /api/rfqs/<id>` - Get RFQ details
- `GET /api/rfqs/<id>/download` - Download .docx file
- `POST /api/rfqs/<id>/regenerate` - Regenerate single RFQ
- `POST /api/rfqs/batch-regenerate` - Regenerate multiple RFQs

### Vendors
- `GET /api/vendors` - List all vendor submissions
- `GET /api/vendors/stats` - Get vendor statistics
- `GET /api/vendors/by-product` - Group vendors by product

### Automation
- `GET /api/automation/status` - Get automation status
- `GET /api/automation/logs` - Get recent logs

## Pages

### Home (`/`)
- Statistics cards (solicitations, RFQs, vendors)
- Quick action buttons
- Recent activity

### Solicitations (`/solicitations`)
- Searchable table
- Pagination
- Contract details

### RFQ Management (`/rfqs`)
- View all generated RFQs
- Download .docx files
- Regenerate individual or batch RFQs
- Quality scores

### Vendor Tracking (`/vendors`)
- All ThomasNet submissions
- Group by vendor or product
- Statistics dashboard

### Automation Control (`/automation`)
- Real-time status
- Manual triggers
- Log viewer

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML + Alpine.js + Tailwind CSS
- **Database**: SQLite
- **Charts**: Planned (Chart.js)

## Integration

The dashboard automatically integrates with:
- Existing `database_manager.py`
- `run_complete_automation.py`
- ThomasNet automation logs

## Next Steps

To fully enable vendor tracking, update `ThomasNetAgent`:

```python
# In thomasnet_agent.py, after successful submission:
from database_manager import DatabaseManager

db = DatabaseManager()
db.add_thomasnet_submission(
    contract_id=contract_id,
    vendor_name=vendor_info['name'],
    vendor_company=vendor_info['company'],
    vendor_location=vendor_info.get('location', ''),
    product_searched=product,
    rfq_file_path=rfq_path,
    success=True
)
```

## Screenshots

### Dashboard Home
[Will show stats cards and recent activity]

### RFQ Management
[Will show table with download/regenerate options]

### Vendor Tracking
[Will show vendor submissions grouped by product]

---

**Happy Managing!** 🚀
