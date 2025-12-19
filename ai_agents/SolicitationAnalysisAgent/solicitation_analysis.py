import os
import sys
import urllib.request
import urllib.error
import json

print("DEBUG: Subprocess Trace - Started (Urllib)", file=sys.stderr, flush=True)

# Add the parent directory to the Python path to allow imports from other agent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Mock-Shim to prevent config.py and AttachmentReaderAgent from hanging on google.generativeai import
from unittest.mock import MagicMock
print("DEBUG: Subprocess Trace - Patching GenAI", file=sys.stderr, flush=True)
sys.modules['google.generativeai'] = MagicMock()
import config
print("DEBUG: Subprocess Trace - Config imported", file=sys.stderr, flush=True)
# del sys.modules['google.generativeai'] # KEEP MOCKED to prevent AttachmentReaderAgent from hanging
# del sys.modules['google.generativeai'] # KEEP MOCKED to prevent AttachmentReaderAgent from hanging

def analyze_solicitation(solicitation):
    print("DEBUG: Subprocess Trace - Analyzing...", file=sys.stderr, flush=True)
    """
    Analyzes a solicitation using the generative model via REST API.
    """
    # Use description from DB if available, otherwise we can't do much without Selenium
    details = solicitation.get('description', '')
    contract_id = solicitation.get('contract_id')
    
    # Deep Analysis Integration
    if contract_id:
        try:
            print("DEBUG: Subprocess Trace - Attachment Analysis DISABLED to prevent import hang", file=sys.stderr, flush=True)
            # print("DEBUG: Subprocess Trace - Importing AttachmentReaderAgent", flush=True)
            # from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
            # print("DEBUG: Subprocess Trace - AttachmentReaderAgent imported", flush=True)
            # reader = AttachmentReaderAgent()
            # base_dir = f"data/solicitations/{contract_id}"
            
            # # Read Attachments
            # att_dir = os.path.join(base_dir, "attachments")
            # if os.path.exists(att_dir):
            #     for fname in os.listdir(att_dir):
            #         fpath = os.path.join(att_dir, fname)
            #         # print(f"Reading attachment: {fname}")
            #         # content = reader._read_file_content(fpath)
            #         # if content:
            #         #     details += f"\n\n--- ATTACHMENT: {fname} ---\n{content[:50000]}" # Limit size per file

            # # Read Linked Pages
            # link_dir = os.path.join(base_dir, "linked_pages")
            # if os.path.exists(link_dir):
            #      for fname in os.listdir(link_dir):
            #         fpath = os.path.join(link_dir, fname)
            #         # print(f"Reading linked page: {fname}")
            #         # content = reader._read_file_content(fpath)
            #         # if content:
            #         #     details += f"\n\n--- LINKED PAGE CONTENT: {fname} ---\n{content[:50000]}"
            pass
                        
        except Exception as e:
            print(f"Warning: Could not read extra files for analysis: {e}")
                        
        except Exception as e:
            print(f"Warning: Could not read extra files for analysis: {e}")
    
    if not details or len(details) < 50:
        return "Insufficient details in database and scraper unavailable.", None

    prompt = f"""
    You are a 'Solicitation Analysis Agent'. Your task is to analyze a government contract solicitation.
    
    DATA SOURCES:
    The content below includes the main solicitation description, text from verification links, and content extracted from attached documents (PDFs, Excel, etc.).
    
    --- START OF CONTENT ---
    {details[:100000]} 
    --- END OF CONTENT ---
    
    Your goal is to STRICTLY distinguish between physical PRODUCTS (goods, equipment, supplies) and SERVICES (labor, maintenance, consulting, construction).
    
    STEP 1: CLASSIFY
    Determine the primary nature of this contract.
    - PRODUCT: Buying physical goods (e.g. "500 Laptops", "Steel Beams", "Medical Kits", "Spare Parts").
    - SERVICE: Buying labor or expertise (e.g. "Mowing", "Cleaning", "Consulting", "Repair Services", "Maintenance").
    - CONSTRUCTION: Building or repairing infrastructure (e.g. "Repaving road", "Roof replacement").

    STEP 2: EXTRACT
    - If Category is 'SERVICE' or 'CONSTRUCTION': Set "products" to an empty list []. Do NOT extract items.
    - If Category is 'PRODUCT': Extract the specific items requested.

    Output ONLY a valid JSON object with the following structure:
    {{
        "solicitation_number": "Stated or N/A",
        "due_date": "YYYY-MM-DD or N/A",
        "location": "City, State, or Place of Performance (e.g. 'Virginia', 'San Diego, CA')",
        "summary": "Brief 1-sentence summary of what is being requested.",
        "category": "PRODUCT" | "SERVICE" | "CONSTRUCTION",
        "primary_application": "The industry or use case (e.g. 'Aerospace', 'Medical', 'General Constr')",
        "products": [
            {{
                "name": "Specific Product Name",
                "quantity": "Quantity required (integer or string). SEARCH HARD FOR THIS.",
                "specifications": "Key technical specs, dimensions, materials, part numbers found in text/attachments.",
                "description": " Detailed description.",
                "naics_code": "NAICS code if mentioned",
                "source_file": "Filename if extracted from an attachment, else 'Description'",
                "thomasnet_search_terms": ["Broad Term 1", "Specific Term 2"]
            }}
        ],
        "confidence_score": 0.0 to 1.0 (Float),
        "confidence_reasoning": "Explain classification and extraction confidence."
    }}
    """

    if config.GEMINI_API_KEY:
        api_key = config.GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Construct the payload
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        try:
            # Use urllib instead of requests to avoid import hangs
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=60) as response:
                response_text = response.read().decode('utf-8')
                result_json = json.loads(response_text)

            try:
                text = result_json['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                return f"Error parsing API response: {json.dumps(result_json)}", 0.0

            # Calculate Confidence from extracted JSON
            confidence = 1.0
            try:
                # Strip markdown if present
                clean_text = text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_text)
                
                # Logic Check
                if data.get('category') in ['SERVICE', 'CONSTRUCTION']:
                    pass
                elif not data.get('products'):
                    confidence -= 0.5
                else:
                    for prod in data['products']:
                        if not prod.get('quantity') or prod.get('quantity') == "Unspecified":
                            confidence -= 0.1
                        if not prod.get('specifications'):
                            confidence -= 0.1
                
                confidence = max(0.0, confidence)
                
            except json.JSONDecodeError:
                confidence = 0.0 # Failed to parse output JSON
                
            return text, confidence

        except urllib.error.URLError as e:
            return f"API Request Failed (URLError): {e}", 0.0
        except Exception as e:
            return f"API Request Failed (Exception): {e}", 0.0
    else:
        return {"error": "Gemini API Key missing"}, 0.0

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Run Solicitation Analysis')
    parser.add_argument('--data', type=str, help='Solicitation data as JSON string')
    args = parser.parse_args()
    
    if args.data:
        try:
            sol_data = json.loads(args.data)
            # Suppress logs during analysis to keep stdout clean for JSON result
            import sys
            sys.stdout = sys.stderr
            
            # Run Analysis
            result_text, confidence = analyze_solicitation(sol_data)
            
            # Restore stdout
            sys.stdout = sys.__stdout__
            
            # Output Result as JSON
            output = {
                "text": result_text,
                "confidence": confidence
            }
            print(json.dumps(output))
            
        except Exception as e:
            sys.stdout = sys.__stdout__
            print(json.dumps({"error": str(e), "confidence": 0.0}))
    else:
        # Legacy test
        example_solicitation = {
            "title": "Temporary Portable Steel Logging Bridge",
            "url": "https://sam.gov/opp/d8f9b6a8b7c14a1b8b8b8b8b8b8b8b8b/view"
        }
        print(f"--- Running SolicitationAnalysisAgent for: {example_solicitation['title']} ---")
        analysis = analyze_solicitation(example_solicitation)
        print("\n--- Solicitation Analysis Results ---")
        print(analysis)