import time
import sys
import logging
from run_email_campaign import run_campaign

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ContinuousCampaign")

def run_batches(batch_size=10, delay=10):
    logger.info(f"--- Starting Continuous Email Campaign (Batch Size: {batch_size}) ---")
    
    total_processed = 0
    while True:
        try:
            processed = run_campaign(batch_size)
            total_processed += processed
            
            if processed == 0:
                logger.info("No pending tasks processed in this batch. Queue empty.")
                break
                
            logger.info(f"Batch complete. Validated {processed} items. Sleeping for {delay} seconds...")
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"Critical Loop Error: {e}")
            time.sleep(30) # Wait a bit before retry on crash
            
    logger.info(f"--- Continuous Campaign Finished. Total Processed: {total_processed} ---")

if __name__ == "__main__":
    run_batches(10, 5) # Batch 10, 5s delay between batches (on top of inner delay)
