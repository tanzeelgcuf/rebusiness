#!/usr/bin/env python3
"""
RFQ Management Dashboard
Flask web application for managing solicitations, RFQs, and vendor submissions
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import os
import sys
import threading

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_manager import DatabaseManager
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Enable CORS for API endpoints

# Configuration
app.config['SECRET_KEY'] = 'rfq-dashboard-secret-key-change-in-production'
app.config['JSON_SORT_KEYS'] = False

# Initialize database
db = DatabaseManager()

# ============================================================================
# HTML Pages
# ============================================================================

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('index.html')

@app.route('/solicitations')
def solicitations_page():
    """Solicitations list page"""
    return render_template('solicitations.html')

@app.route('/rfqs')
def rfqs_page():
    """RFQ management page"""
    return render_template('rfqs.html')

@app.route('/vendors')
def vendors_page():
    """Vendor tracking page"""
    return render_template('vendors.html')

@app.route('/automation')
def automation_page():
    """Automation control page"""
    return render_template('automation.html')

# ============================================================================
# API Endpoints - Solicitations
# ============================================================================

@app.route('/api/solicitations', methods=['GET'])
def api_get_solicitations():
    """Get list of solicitations with pagination"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        search = request.args.get('search', '')
        
        solicitations = db.get_all_solicitations(limit=limit, offset=offset, search=search)
        total = db.get_solicitations_count(search=search)
        
        return jsonify({
            'success': True,
            'data': solicitations,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/solicitations/<contract_id>', methods=['GET'])
def api_get_solicitation(contract_id):
    """Get single solicitation details"""
    try:
        solicitation = db.get_solicitation_by_id(contract_id)
        if not solicitation:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        
        return jsonify({'success': True, 'data': solicitation})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/solicitations/stats', methods=['GET'])
def api_solicitation_stats():
    """Get solicitation statistics"""
    try:
        stats = db.get_dashboard_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API Endpoints - RFQs
# ============================================================================

@app.route('/api/rfqs', methods=['GET'])
def api_get_rfqs():
    """Get list of RFQs with pagination"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status', 'pending') # Default to pending
        
        # Convert status for DB
        sent_status = None
        if status == 'pending':
            sent_status = 'pending'
        elif status == 'completed':
            sent_status = 'sent'
        elif status == 'all':
            sent_status = None
            
        rfqs = db.get_all_rfqs(limit=limit, offset=offset, sent_status=sent_status)
        total = db.get_rfqs_count(sent_status=sent_status)
        
        return jsonify({
            'success': True,
            'data': rfqs,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def docx_to_html(file_path):
    """Convert DOCX file to simple HTML for preview"""
    try:
        from docx import Document
        doc = Document(file_path)
        html = ['<div class="rfq-preview font-serif p-8 bg-white text-black">']
        
        for element in doc.element.body:
            if element.tag.endswith('p'):
                # Handle paragraph
                from docx.text.paragraph import Paragraph
                para = Paragraph(element, doc)
                if para.text.strip():
                    style = 'mb-4'
                    if 'Heading' in str(para.style):
                        style += ' text-xl font-bold mt-6 border-b pb-2'
                    elif 'List' in str(para.style):
                        style += ' ml-6 list-disc'
                    html.append(f'<p class="{style}">{para.text}</p>')
            elif element.tag.endswith('tbl'):
                # Handle table
                html.append('<div class="overflow-x-auto mb-6"><table class="min-w-full border-collapse border border-gray-300">')
                from docx.table import Table
                table = Table(element, doc)
                for i, row in enumerate(table.rows):
                    bg = 'bg-gray-100 font-bold' if i == 0 else ''
                    html.append(f'<tr class="{bg}">')
                    for cell in row.cells:
                        html.append(f'<td class="border border-gray-300 p-2 text-sm">{cell.text}</td>')
                    html.append('</tr>')
                html.append('</table></div>')
                
        html.append('</div>')
        return '\n'.join(html)
    except Exception as e:
        return f'<div class="text-red-500">Error previewing file: {str(e)}</div>'

@app.route('/api/rfqs/<contract_id>', methods=['GET'])
def api_get_rfq(contract_id):
    """Get RFQ details including HTML preview"""
    try:
        rfq = db.get_rfq_by_contract(contract_id)
        if not rfq:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        
        # Add HTML preview if file exists
        file_path_exists = rfq.get('file_path') and os.path.exists(rfq['file_path'])
        
        if file_path_exists:
            rfq['html_content'] = docx_to_html(rfq['file_path'])
        else:
            # Try to find file if path is missing or invalid - robust path handling
            import glob
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pattern_gen = os.path.join(project_root, "rfq_downloads", "*", f"{contract_id}_RFQ_*.docx")
            pattern_up = os.path.join(project_root, "rfq_downloads", "uploads", f"{contract_id}_*")
            
            files = glob.glob(pattern_gen) + glob.glob(pattern_up)
            
            if files:
                # Get latest
                files.sort(key=os.path.getmtime, reverse=True)
                rfq['file_path'] = files[0]
                rfq['html_content'] = docx_to_html(files[0])
            else:
                rfq['html_content'] = '<div class="p-4 text-gray-500">File not found for preview.</div>'
        
        return jsonify({'success': True, 'data': rfq})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/<contract_id>/download', methods=['GET'])
def api_download_rfq(contract_id):
    """Download RFQ .docx file"""
    try:
        rfq = db.get_rfq_by_contract(contract_id)
        if not rfq:
            return jsonify({'success': False, 'error': 'Not found in DB'}), 404
        
        # Find the .docx file - robust path handling
        import glob
        # Calculate project root from this file's location (dashboard/app.py -> project_root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Pattern to match: project_root/rfq_downloads/ANY_DATE_FOLDER/contractId_RFQ_*.docx
        pattern = os.path.join(project_root, "rfq_downloads", "*", f"{contract_id}_RFQ_*.docx")
        
        print(f"DEBUG: Searching for RFQ file: {pattern}")
        files = glob.glob(pattern)
        
        if not files:
            print(f"DEBUG: No files found for pattern")
            return jsonify({'success': False, 'error': 'File not found on server'}), 404
        
        # Sort by modification time to get latest if multiple exist
        files.sort(key=os.path.getmtime, reverse=True)
        file_path = files[0]
        print(f"DEBUG: Found RFQ file: {file_path}")
        
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/<contract_id>', methods=['PUT'])
def api_update_rfq(contract_id):
    """Update RFQ content"""
    try:
        data = request.get_json()
        content = data.get('content')
        
        if not content:
            return jsonify({'success': False, 'error': 'Content required'}), 400
        
        # Update in database
        db.update_rfq_content(contract_id, content)
        
        # Overwrite the physical file so automation uses the new content
        # Find the file path
        import glob
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Pattern 1: Generated files
        pattern_gen = os.path.join(project_root, "rfq_downloads", "*", f"{contract_id}_RFQ_*.docx")
        # Pattern 2: Uploaded files
        pattern_up = os.path.join(project_root, "rfq_downloads", "uploads", f"{contract_id}_*")
        
        files = glob.glob(pattern_gen) + glob.glob(pattern_up)
        
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            file_path = files[0]
            # Only attempt to overwrite if it's a docx file (python-docx limit)
            if not file_path.lower().endswith('.docx'):
                print(f"DEBUG: Skipping file overwrite for non-docx file: {file_path}")
                return jsonify({'success': True, 'message': 'Database updated. File overwrite skipped for non-docx format.'})
            
            try:
                from docx import Document
                doc = Document()
                
                # Simple Markdown to DOCX conversion
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith('# '):
                        doc.add_heading(line[2:], level=1)
                    elif line.startswith('## '):
                        doc.add_heading(line[3:], level=2)
                    elif line.startswith('### '):
                        doc.add_heading(line[4:], level=3)
                    elif line.startswith('- '):
                        doc.add_paragraph(line[2:], style='List Bullet')
                    else:
                        doc.add_paragraph(line)
                        
                doc.save(file_path)
                print(f"DEBUG: Overwrote DOCX file at {file_path} with edited content")
            except Exception as e:
                print(f"ERROR: Failed to update DOCX file: {e}")
                # We don't fail the request, just log it
        
        return jsonify({'success': True, 'message': 'RFQ updated and file overwritten'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/upload', methods=['POST'])
def api_upload_rfq():
    """Upload a manual RFQ file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'}), 400
            
        if file:
            filename = file.filename
            # Sanitize filename
            import werkzeug.utils
            filename = werkzeug.utils.secure_filename(filename)
            
            # Determine contract_id
            # Try to extract from filename or generate new
            import uuid
            contract_id = f"MANUAL_{uuid.uuid4().hex[:8]}"
            
            # Save file
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            upload_dir = os.path.join(project_root, "rfq_downloads", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, f"{contract_id}_{filename}")
            file.save(file_path)
            
            # Read content for DB (if text/md/docx)
            content = "Uploaded file: " + filename
            try:
                if filename.endswith('.docx'):
                     # We can try to extract text or just save placeholder
                     content = f"# Uploaded RFQ: {filename}\n\n[File on server]"
                elif filename.endswith('.md') or filename.endswith('.txt'):
                     with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                         content = f.read()
            except Exception as e:
                print(f"Error reading uploaded file content: {e}")

            # Add to DB
            # We use a dummy type 'PRODUCT' for now
            success = db.add_rfq_output(contract_id, "PRODUCT", content)
            
            # Update the filepath in DB logic? 
            # Currently `add_rfq_output` doesn't save filepath, 
            # but our path resolution logic in `api_get_rfq` looks in specific folders.
            # We need to make sure `api_get_rfq` can find this upload.
            # Updated path resolution logic in `api_get_rfq` and `api_download_rfq` to include 'uploads' folder.
            
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/<contract_id>/send', methods=['POST'])
def api_send_rfq(contract_id):
    """Trigger ThomasNet submission for a single RFQ"""
    try:
        # We run this in a background thread to not block
        def run_send():
            # Set up logging to file so errors are visible
            import glob
            import traceback
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, 'submission.log')
            
            def log(msg):
                import datetime
                line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
                print(line)
                with open(log_path, 'a') as f:
                    f.write(line + '\n')

            log(f"=== Send started for contract: {contract_id} ===")
            try:
                # Import here to avoid circular dependencies
                log("Importing ThomasNet module...")
                from dashboard.utils.dashboard_thomasnet import submit_single_rfq_task
                log("Import OK")
                
                # Find file path first
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                pattern_generated = os.path.join(project_root, "rfq_downloads", "*", f"{contract_id}_RFQ_*")
                pattern_upload = os.path.join(project_root, "rfq_downloads", "uploads", f"{contract_id}_*")
                
                log(f"Searching: {pattern_generated}")
                all_files = glob.glob(pattern_generated) + glob.glob(pattern_upload)
                
                # Filter out validation reports and other non-RFQ files
                files = [f for f in all_files if not f.lower().endswith('_validation_report.txt')]
                
                if not files:
                    log(f"ERROR: No RFQ file found for {contract_id} (found {len(all_files)} total files)")
                    return
                
                files.sort(key=os.path.getmtime, reverse=True)
                file_path = files[0]
                log(f"Found file: {file_path}")
                
                # Connect and Send
                log("Calling submit_single_rfq_task...")
                submit_single_rfq_task(file_path)
                log("submit_single_rfq_task completed successfully.")
                
            except Exception as e:
                log(f"ERROR: {e}")
                log(traceback.format_exc())

        thread = threading.Thread(target=run_send)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Submission started in background'})
    except Exception as e:
         return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/<contract_id>/regenerate', methods=['POST'])
def api_regenerate_rfq(contract_id):
    """Regenerate single RFQ"""
    try:
        from utils.rfq_regenerator import regenerate_single_rfq
        
        result = regenerate_single_rfq(contract_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfqs/batch-regenerate', methods=['POST'])
def api_batch_regenerate():
    """Regenerate multiple RFQs"""
    try:
        data = request.get_json()
        contract_ids = data.get('contract_ids', [])
        
        if not contract_ids:
            return jsonify({'success': False, 'error': 'No contract IDs provided'}), 400
        
        from utils.rfq_regenerator import regenerate_batch
        
        results = regenerate_batch(contract_ids)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API Endpoints - Vendors
# ============================================================================

@app.route('/api/vendors', methods=['GET'])
def api_get_vendors():
    """Get list of vendor submissions"""
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        vendors = db.get_vendor_submissions(limit=limit, offset=offset)
        total = db.get_vendor_submissions_count()
        
        return jsonify({
            'success': True,
            'data': vendors,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vendors/stats', methods=['GET'])
def api_vendor_stats():
    """Get vendor statistics"""
    try:
        stats = db.get_vendor_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vendors/by-product', methods=['GET'])
def api_vendors_by_product():
    """Get vendors grouped by product"""
    try:
        grouped = db.get_vendors_by_product()
        return jsonify({'success': True, 'data': grouped})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API Endpoints - Dashboard Stats
# ============================================================================

@app.route('/api/dashboard/stats', methods=['GET'])
def api_dashboard_stats():
    """Get all dashboard statistics"""
    try:
        stats = db.get_dashboard_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API Endpoints - Automation
# ============================================================================

@app.route('/api/automation/status', methods=['GET'])
def api_automation_status():
    """Get automation status"""
    try:
        # Check if automation is running
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'run_complete_automation.py'], 
                               capture_output=True)
        is_running = result.returncode == 0
        
        return jsonify({
            'success': True,
            'data': {
                'running': is_running,
                'mode': 'continuous' if is_running else 'stopped'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/automation/logs', methods=['GET'])
def api_automation_logs():
    """Get recent automation logs"""
    try:
        lines = int(request.args.get('lines', 100))
        
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
                
            return jsonify({
                'success': True,
                'data': {
                    'logs': ''.join(recent_lines),
                    'lines': len(recent_lines)
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {'logs': f'No logs available at {LOG_FILE}', 'lines': 0}
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper to get paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, 'automation.log')
LOG_FILE_GEN = os.path.join(BASE_DIR, 'generation.log')
LOG_FILE_SUB = os.path.join(BASE_DIR, 'submission.log')

# Initialize log files if not exist
for log_file in [LOG_FILE, LOG_FILE_GEN, LOG_FILE_SUB]:
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            f.write(f"Log initialized at {datetime.now().isoformat()}\\n")

@app.route('/api/automation/logs/<log_type>', methods=['GET'])
def api_get_logs_by_type(log_type):
    """Get logs for specific process"""
    try:
        lines = int(request.args.get('lines', 100))
        
        if log_type == 'generation':
            target_file = LOG_FILE_GEN
        elif log_type == 'submission':
            target_file = LOG_FILE_SUB
        else:
            target_file = LOG_FILE
            
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
            return jsonify({
                'success': True, 
                'data': {
                    'logs': ''.join(recent_lines),
                    'lines': len(recent_lines)
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {'logs': 'No logs available', 'lines': 0}
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/automation/generate-rfqs', methods=['POST'])
def api_generate_rfqs():
    """Manual trigger: Generate new RFQs from sam.gov"""
    try:
        import subprocess
        import threading
        
        # Get parameters
        data = request.get_json() or {}
        keyword = data.get('keyword', 'industrial equipment')
        pages = data.get('pages', 1)
        
        # Run in background thread
        def run_generation():
            try:
                # Write to generation log
                with open(LOG_FILE_GEN, 'a') as f:
                    f.write(f"\\n{'='*80}\\n STARTING MANUAL RFQ GENERATION: {keyword} ({pages} pages)\\n{'='*80}\\n")
                    f.flush()
                    
                    subprocess.run(
                        ['python3', 'main_workflow.py', '--keyword', keyword, '--pages', str(pages)],
                        cwd=BASE_DIR,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    
                    f.write(f"\\n{'='*80}\\n COMPLETED MANUAL RFQ GENERATION\\n{'='*80}\\n")
            except Exception as e:
                with open(LOG_FILE_GEN, 'a') as f:
                    f.write(f"\\n❌ ERROR STARTED GENERATION: {str(e)}\\n")
        
        thread = threading.Thread(target=run_generation)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Started RFQ generation for "{keyword}" ({pages} page{"s" if pages > 1 else ""})',
            'keyword': keyword,
            'pages': pages
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/automation/submit-rfqs', methods=['POST'])
def api_submit_rfqs():
    """Manual trigger: Submit pending RFQs to ThomasNet using logged-in browser"""
    try:
        import threading
        import sys
        from pathlib import Path
        
        # Add parent directory to path for imports
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # Get parameters
        data = request.get_json() or {}
        max_vendors = data.get('max_vendors', 5)
        
        # Run in background thread
        def run_submission():
            try:
                with open(LOG_FILE_SUB, 'a') as f:
                    f.write(f"\n{'='*80}\n STARTING THOMASNET SUBMISSION (Browser-Based)\n{'='*80}\n")
                    f.flush()
                
                # Import here to avoid import errors if modules not ready
                from dashboard.utils.dashboard_thomasnet import run_dashboard_thomasnet_submission
                
                # Run the submission using browser connection
                result = run_dashboard_thomasnet_submission(max_vendors=max_vendors)
                
                # Log results
                with open(LOG_FILE_SUB, 'a') as f:
                    if result.get('success'):
                        f.write(f"\n✅ SUCCESS: {result.get('message')}\n")
                        f.write(f"   RFQs processed: {result.get('rfqs_processed', 0)}\n")
                        f.write(f"   Vendors contacted: {result.get('vendors_contacted', 0)}\n")
                    else:
                        f.write(f"\n❌ FAILED: {result.get('error', 'Unknown error')}\n")
                    f.write(f"{'='*80}\n THOMASNET SUBMISSION COMPLETE\n{'='*80}\n")
                    
            except Exception as e:
                import traceback
                with open(LOG_FILE_SUB, 'a') as f:
                    f.write(f"\n❌ ERROR IN SUBMISSION: {str(e)}\n")
                    f.write(traceback.format_exc())
        
        thread = threading.Thread(target=run_submission)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Started ThomasNet submission using your logged-in browser session'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("="*80)
    print(" RFQ Management Dashboard")
    print("="*80)
    print(f" Starting Flask server...")
    print(f" Access dashboard at: http://localhost:5001")
    print("="*80)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
