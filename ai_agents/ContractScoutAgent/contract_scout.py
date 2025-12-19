import os
import sys

# Add the parent directory to the Python path to allow imports from other agent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ai_agents.SamGovAgent.sam_gov_agent import SamGovAgent

def find_contract_opportunities(search_term, sam_gov_agent):
    """
    Finds contract opportunities for a given search term by using the SamGovAgent.

    Args:
        search_term (str): The search term (NAICS code or keyword) to search for.
        sam_gov_agent (SamGovAgent): An initialized and logged-in SamGovAgent instance.

    Returns:
        list: A list of solicitation dictionaries.
    """
    solicitations = sam_gov_agent.search_solicitations(search_term)
    return solicitations

if __name__ == "__main__":
    # Example search by NAICS code
    search_term_naics = "423000" # Example NAICS code for "Durable Goods"
    print(f"--- Running ContractScoutAgent for search term: {search_term_naics} ---")
    opportunities_by_naics = find_contract_opportunities(search_term_naics)
    print("\n--- Contract Scout Results (by NAICS) ---")
    print(opportunities_by_naics)

    # Example search by keywords
    search_term_keywords = "IT consulting"
    print(f"--- Running ContractScoutAgent for search term: {search_term_keywords} ---")
    opportunities_by_keywords = find_contract_opportunities(search_term_keywords)
    print("\n--- Contract Scout Results (by Keywords) ---")
    print(opportunities_by_keywords)