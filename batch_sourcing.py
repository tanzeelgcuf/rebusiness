import sys
import time
import json
import subprocess
import os
from database_manager import DatabaseManager
from ai_agents.OutreachAgent.form_filler import OutreachAgent

# Setup
db_manager = DatabaseManager()
outreach_agent = OutreachAgent()

def run_sourcing_batch():
    print("--- Starting Batch Sourcing for Pending Products ---", flush=True)
    
    # 1. Fetch products needing sourcing
    products = db_manager.get_products_for_sourcing(limit=100) # Process all/chunk
    print(f"Found {len(products)} products to source.", flush=True)
    
    for p in products:
        p_id = p['id']
        p_name = p['product_name']
        print(f"\n> Sourcing: {p_name} (ID: {p_id})", flush=True)
        
        # Update status to sourcing
        db_manager.update_sourcing_status(p_id, status='sourcing')
        
        # 2. Call ThomasNetAgent (via subprocess to match main_workflow style and use CLI args)
        try:
            cmd = [
                sys.executable, 
                os.path.join('ai_agents', 'ThomasNetAgent', 'thomasnet_agent.py'),
                '--search', p_name,
                '--limit', '20' 
            ]
            print(f"  Executing agent for {p_name}...", flush=True)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            suppliers = []
            if result.returncode == 0:
                # Parse JSON output
                try:
                    lines = result.stdout.strip().split('\n')
                    # Find the JSON line (usually the last one)
                    json_line = next((line for line in reversed(lines) if line.startswith('[') and line.endswith(']')), "[]")
                    suppliers = json.loads(json_line)
                except Exception as e:
                    print(f"  Failed to parse agent output: {e}")
            else:
                print(f"  Agent failed: {result.stderr}")

            print(f"  Found {len(suppliers)} suppliers.", flush=True)
            
            # 3. Save Suppliers
            found_count = 0
            for s in suppliers:
                manufacturer_id = db_manager.add_manufacturer(
                    name=s['name'],
                    website=s['website'],
                    email=s.get('email'),
                    phone=s.get('phone'),
                    address=s.get('location')
                )
                if manufacturer_id:
                    db_manager.link_product_supplier(p_id, manufacturer_id)
                    found_count += 1
            
            # 4. Trigger Outreach immediately? (Or separate loop?)
            # User workflow implies finding then doing outreach. Let's do it here.
            # Actually, let's keep it separate or just log it.
            # outreach_agent.process_product_outreach(p_id) # Hypothetical method
            
            # Update status
            db_manager.update_sourcing_status(p_id, status='sourcing_complete', found_inc=found_count)
            
            time.sleep(2) # Polite delay
            
        except Exception as e:
            print(f"  Error processing {p_name}: {e}")

    print("\n--- Batch Sourcing Complete ---", flush=True)

if __name__ == "__main__":
    run_sourcing_batch()
