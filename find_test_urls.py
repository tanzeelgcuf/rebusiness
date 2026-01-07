from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('find_test_urls')

def main():
    agent = SamGovAgent()
    agent.start_browser()

    try:
        # Find Service URL
        logger.info("Searching for SERVICE solicitation (keyword: 'mowing')...")
        service_links = agent.search_for_links("mowing", num_pages=1)
        if service_links:
            # Filter for likely opportunities (exclude pre-solicitations if possible, though search usually returns opps)
            valid_service = [l for l in service_links if "/opp/" in l]
            if valid_service:
                print(f"\nFOUND SERVICE URL: {valid_service[0]}")
            else:
                print("\nNo valid service URLs found.")
        else:
             print("\nNo service links found.")

        # Find Product URL
        logger.info("Searching for PRODUCT solicitation (keyword: 'adapter')...")
        product_links = agent.search_for_links("adapter", num_pages=1)
        if product_links:
            valid_product = [l for l in product_links if "/opp/" in l]
            if valid_product:
                 print(f"\nFOUND PRODUCT URL: {valid_product[0]}")
            else:
                print("\nNo valid product URLs found.")
        else:
             print("\nNo product links found.")

    finally:
        agent.close()

if __name__ == "__main__":
    main()
