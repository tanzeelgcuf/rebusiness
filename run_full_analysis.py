from database_manager import DatabaseManager
from ai_agents.SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation
import logging
import json
import time

logging.basicConfig(level=logging.INFO)

def run():
    db = DatabaseManager()
    solicitations = db.get_all_solicitations()
    
    print(f"Found {len(solicitations)} solicitations.")
    
    for sol in solicitations:
        contract_id = sol['contract_id']
        title = sol['title']
        print(f"Analyzing: {title} ({contract_id})...")
        
        # Convert row to dict
        sol_dict = dict(sol)
        # Note: analyze_solicitation handles SamGov scraping internally
        try:
            analysis_result, confidence = analyze_solicitation(sol_dict)
            
            # Determine Review Status
            review_status = 'pending'
            if confidence is None or confidence < 0.8:
                review_status = 'flagged'
            else:
                review_status = 'reviewed' # Auto-approved if high confidence
            
            # Update DB with new analysis (JSON format)
            db.add_solicitation_analysis(contract_id, analysis_result, confidence, review_status)
            print(f" -> Analysis updated. Confidence: {confidence:.2f} | Status: {review_status}")
            
        except Exception as e:
            print(f" -> Error analyzing {contract_id}: {e}")

if __name__ == "__main__":
    run()
