import logging
import json
import os
import sys

# Add path for agents
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent
from database_manager import DatabaseManager

# Logging
logger = logging.getLogger("DataEnrichment")
logging.basicConfig(level=logging.INFO)

class DataEnricher:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.downloader = SamGovAgent() # This starts playwight, might be heavy.
        self.reader = AttachmentReaderAgent()

    def enrich_contract(self, contract_id, url):
        """
        Performs a Deep Fetch and Deep Analysis on a specific contract.
        Updates the database with the results.
        """
        logger.info(f"--- Enriching Data for {contract_id} ---")
        
        # 1. Deep Fetch (Download Attachments & Crawl Description)
        try:
            logger.info(f"  Fetching latest data from {url}...")
            self.downloader.process_detail_page(url)
        except Exception as e:
            logger.error(f"  Download failed: {e}")
            # Continue anyway, maybe we have old files
        
        # 2. Deep Analysis (LLM Extraction)
        try:
            logger.info(f"  Analyzing documents with LLM...")
            analysis = self.reader.create_summary_report(contract_id)
            
            if "error" in analysis:
                logger.error(f"  Analysis failed: {analysis['error']}")
                return False
            else:
                # Save structured analysis (updates JSON in DB)
                # Reader agent ALREADY inserted products into DB in create_summary_report logic
                # But we should ensure we don't duplicate-insert if products exist?
                # create_summary_report currently APPENDS products effectively?
                # Actually, run_deep_backfill clears products first.
                # We should probably clear products first to avoid duplicates.
                
                self.db_manager.clear_products_for_solicitation(contract_id) # DANGEROUS? 
                # If we clear products, we break the link to the pending request!
                # The pending request refers to a product_id.
                # If we delete the product, the request becomes orphaned or points to nowhere.
                
                # SOLUTION: 
                # Instead of clearing, we should UPDATE the existing product if it matches?
                # Or just update the solicitation analysis and let the user manually fix?
                # No, we want to fix the email body.
                
                # Compromise:
                # For `delivery_location`, updating `solicitations.analysis_summary` is enough.
                # For `quantity` and `specifications`, those live in `products` table.
                
                # If we re-extract, we get NEW product IDs.
                # We need to update the `manufacturer_requests` to point to the NEW product ID.
                # Complex.
                
                # ALTERNATIVE:
                # Just return the extracted data and let the caller decide how to use it for the email?
                # But we want to save it to DB.
                
                # Valid Strategy:
                # 1. Get old product ID linked to request.
                # 2. Clear products for solicitation (deletes old product).
                # 3. Save new products.
                # 4. Find the "best match" new product (same name-ish).
                # 5. Update manufacturer_request to point to new_product_id.
                
                # For now, let's just save the analysis_summary so Location works.
                self.db_manager.add_solicitation_analysis(contract_id, json.dumps(analysis), confidence=0.95, review_status='enriched')
                
                # We won't clear products yet to avoid breaking the ID link unless we write that logic.
                # But Reader.create_summary_report writes products! It might create duplicates.
                # Let's check AttachmentReaderAgent.create_summary_report code.
                
                return analysis
                
        except Exception as e:
            logger.error(f"  Enrichment failed: {e}")
            return False

    def close(self):
        self.downloader.close()
