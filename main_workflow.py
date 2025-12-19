import os
import sys
import json
import time
import schedule
from unittest.mock import MagicMock

# --- PATCH START ---
print("DEBUG: Patching google.generativeai for imports...", flush=True)
sys.modules['google.generativeai'] = MagicMock()
import config
print("DEBUG: Config imported.", flush=True)

# Add parent directory to path to import ai_agents
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Import Agents (while GenAI is mocked to prevent config hang)
from SamGovAgent.sam_gov_agent import SamGovAgent
print("DEBUG: SamGovAgent imported.", flush=True)
from SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation
print("DEBUG: Analysis Agent imported.", flush=True)
from ThomasNetAgent.thomasnet_agent import ThomasNetAgent
print("DEBUG: ThomasNetAgent imported.", flush=True)
from OutreachAgent.outreach_agent import OutreachAgent
print("DEBUG: OutreachAgent imported.", flush=True)
from database_manager import DatabaseManager
print("DEBUG: DatabaseManager imported.", flush=True)
import nest_asyncio
nest_asyncio.apply()

# Un-patch so lazy loading works later (hopefully)
print("DEBUG: Un-patching google.generativeai...", flush=True)
del sys.modules['google.generativeai']
# --- PATCH END ---

KEYWORD_CHECKPOINT_FILE = "keyword_checkpoint.json"

def process_solicitation(sol_data, db_manager):
    """
    Processes a single solicitation through the analysis, mapping, and outreach steps.
    Assumes scraping and downloading is ALREADY DONE by SamGovAgent.
    """
    contract_id = sol_data.get('contract_id')
    url = sol_data.get('url')
    print(f"\n--- Processing: {sol_data.get('title', 'Unknown')} ({contract_id}) ---")

    # --- Step 1: Deep Analysis ---
    print(f"Running Deep Analysis for {contract_id}...")
    
    # ISOLATION FIX: Run Analysis in a separate process to prevent GenAI hang
    def run_analysis_subprocess(sol_data_dict):
        import subprocess
        import json # Fix free variable error
        try:
            cmd = [
                sys.executable, 
                os.path.join(os.path.dirname(__file__), 'ai_agents', 'SolicitationAnalysisAgent', 'solicitation_analysis.py'),
                '--data', json.dumps(sol_data_dict)
            ]
            # Timeout set to 120 seconds to prevent stalls
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                try:
                    output_json = json.loads(result.stdout.strip())
                    return output_json.get("text", ""), output_json.get("confidence", 0.0)
                except json.JSONDecodeError:
                    print(f"Error decoding analysis JSON output: {result.stdout}")
                    return "Analysis failed (JSON Error)", 0.0
            else:
                print(f"Analysis subprocess failed: {result.stderr}")
                return f"Analysis failed (Exit Code {result.returncode})", 0.0
        except subprocess.TimeoutExpired:
            print("Analysis timed out (120s). Skipping.")
            return "Analysis Timed Out", 0.0
        except Exception as e:
            print(f"Analysis execution error: {e}")
            return f"Analysis Error: {e}", 0.0

    # analyze_solicitation deals with reading attachments/links if they exist in data/solicitations/{id}
    analysis_text, confidence = run_analysis_subprocess(sol_data)
    
    # Save Analysis to DB
    review_status = 'pending'
    if confidence and confidence < 0.8:
        review_status = 'flagged'
        print(f"⚠️ Low confidence ({confidence}). Flagged for review.")
    else:
        review_status = 'reviewed' 
        
    db_manager.add_solicitation_analysis(contract_id, analysis_text, confidence, review_status)
    print("Analysis saved.")

    # --- Step 2: Mapping (Find Suppliers) & Outreach ---
    import json
    try:
        clean_text = analysis_text.replace('```json', '').replace('```', '').strip()
        analysis_json = json.loads(clean_text)
        
        # SHORT CUT: Update the 'data' (JSON) column with our structured analysis so OutreachAgent can read parsed fields
        # like due_date and location.
        db_manager.update_solicitation_data(contract_id, clean_text)

        # STRICT CLASSIFICATION CHECK
        category = analysis_json.get('category', 'PRODUCT').upper()
        if category in ['SERVICE', 'CONSTRUCTION']:
            print(f"⛔ REJECTING: Contract is classified as {category}. Stopping downstream processing.")
            db_manager.add_solicitation_analysis(contract_id, analysis_text, confidence, 'rejected_service')
            return

        # Mapping (Sourcing via ThomasNet)
        print(f"Finding suppliers for products...")
        thomasnet_agent = ThomasNetAgent()
        
        products = analysis_json.get('products', [])
        if not products:
             print("No products extracted to source.")
             return

        for product in products:
            p_name = product.get('name')
            print(f"  > Sourcing: {p_name}")
            
            # 1. SAVE PRODUCT TO DB
            # We need to save the product first to link it later
            product_id = db_manager.add_product(
                contract_id=contract_id,
                product_name=p_name,
                description=product.get('description'),
                specifications=product.get('specifications'),
                quantity=product.get('quantity'),
                naics_code=product.get('naics_code')
            )
            
            # ISOLATION FIX: Run ThomasNet in a separate process
            import subprocess
            try:
                cmd = [
                    sys.executable, 
                    os.path.join(os.path.dirname(__file__), 'ai_agents', 'ThomasNetAgent', 'thomasnet_agent.py'),
                    '--search', p_name,
                    '--limit', '30'
                ]
                print(f"    Executing subprocess: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    json_line = lines[-1] if lines else "[]"
                    try:
                        suppliers = json.loads(json_line)
                    except json.JSONDecodeError:
                        # Regex fallback
                        import re
                        match = re.search(r'\[.*\]', result.stdout, re.DOTALL)
                        suppliers = json.loads(match.group(0)) if match else []
                else:
                    print(f"    Subprocess error: {result.stderr}")
                    suppliers = []
                    
            except Exception as e:
                print(f"    Sourcing execution failed: {e}")
                suppliers = []
            
            # 2. SAVE SUPPLIERS AND LINK
            for s in suppliers:
                # Add to 'manufacturers' table (The source of truth for OutreachAgent)
                manufacturer_id = db_manager.add_manufacturer(
                    name=s['name'],
                    website=s['website'],
                    email=s.get('email'),
                    phone=s.get('phone'),
                    address=s.get('location'), # Map location to address
                    city=None, state=None, zip_code=None, # Parser could extract these later
                    certifications=None, naics_codes=None
                )
                
                if manufacturer_id:
                    # Link Product <-> Manufacturer
                    db_manager.link_product_supplier(product_id, manufacturer_id)
                    # print(f"    Linked {s['name']} to {p_name}")

                # Legacy/Contract linkage (Optional but keeps `vendors` table populated for view)
                db_manager.add_vendor(
                    contract_id=contract_id,
                    name=s['name'],
                    website=s['website'],
                    email=s.get('email'),
                    phone=s.get('phone'),
                    confidence_score=90,
                    has_gov_page=False,
                    has_past_performance=False,
                    gov_agencies_worked_with=None,
                    past_performance_summary=s.get('notes', 'Sourced via ThomasNet'),
                    key_personnel=None,
                    linkedin_url=None,
                    place_types=None,
                    email_status='Ready to Contact'
                )
        
        # Outreach
        print(f"Running OutreachAgent for {contract_id}...")
        outreach_agent = OutreachAgent(db_manager)
        
        vendors = db_manager.get_vendors_for_solicitation(contract_id)
        if vendors:
            for vendor_row in vendors:
                vendor = dict(vendor_row)
                if vendor.get('email') or vendor.get('website'):
                    print(f"--- Contacting {vendor['name']} ---")
                    # OutreachAgent handles message generation + dual channel sending
                    success = outreach_agent.send_outreach(vendor, product_details=analysis_json)
                    if success:
                        print(f" -> Outreach Sent/Drafted ({vendor['name']})")
                    else:
                        print(f" -> Outreach Failed ({vendor['name']})")
                else:
                    print(f"Skipping {vendor['name']} (No Contact Info)")
        else:
            print("No vendors found.")

    except json.JSONDecodeError:
        print("Error: Could not parse analysis JSON. Skipping Mapping/Outreach.")
        return
    except Exception as e:
        print(f"Error in Processing: {e}")
        return


def main_job(db_manager, sam_gov_agent):
    """
    Main Loop: Find -> Scrape -> Analyze -> Map -> Draft
    """
    print("\n\n=== STARTING BATCH JOB ===")

    try:
        # 1. Rotate Keywords
        last_keyword_index = -1
        if os.path.exists(KEYWORD_CHECKPOINT_FILE):
            with open(KEYWORD_CHECKPOINT_FILE, 'r') as f:
                try:
                    checkpoint = json.load(f)
                    last_keyword_index = checkpoint.get('last_keyword_index', -1)
                except json.JSONDecodeError: pass
        
        keywords = config.SEARCH_KEYWORDS
        next_keyword_index = (last_keyword_index + 1) % len(keywords)
        search_keyword = keywords[next_keyword_index]

        with open(KEYWORD_CHECKPOINT_FILE, 'w') as f:
            json.dump({'last_keyword_index': next_keyword_index}, f)
        
        # 2. Run Deep Scraper
        # search_for_new_solicitations handles checkpoints and calls scrape_solicitations (download + crawl)
        print(f"--- KEYWORD: {search_keyword} ---")
        new_solicitations = sam_gov_agent.search_for_new_solicitations(search_keyword)
        
        print(f"--- Found {len(new_solicitations)} new items ---")

        # 3. Process Each
        for sol in new_solicitations:
            contract_id = sol.get('contract_id')
            if not contract_id: continue
            
            # Save basic info to DB first
            if not db_manager.solicitation_exists(contract_id):
                db_manager.add_solicitation(
                    contract_id=contract_id,
                    url=sol['url'],
                    title=sol['title'],
                    description=sol['description'],
                    location="USA",
                    product_requirements=None,
                    analysis_summary=None,
                    data="{}"
                )
                
                # Now trigger the downstream workflow
                process_solicitation(sol, db_manager)
            else:
                print(f"Skipping {contract_id} (Already in DB)")
        
    except Exception as e:
        print(f"CRITICAL JOB ERROR: {e}")

if __name__ == "__main__":
    print("DEBUG: Script started", flush=True)
    db_manager = DatabaseManager()
    print("DEBUG: DB Manager initialized", flush=True)
    sam_gov_agent = None
    try:
        print("DEBUG: Initializing SamGovAgent...", flush=True)
        sam_gov_agent = SamGovAgent()
        print("DEBUG: SamGovAgent initialized", flush=True)
        
        # Run Immediately
        print("DEBUG: Calling main_job...", flush=True)
        main_job(db_manager, sam_gov_agent)

        # Schedule
        schedule.every(3).hours.do(main_job, db_manager=db_manager, sam_gov_agent=sam_gov_agent)

        print("\n--- Scheduler Active (Every 3 Hours) ---")
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        if sam_gov_agent:
            sam_gov_agent.close()