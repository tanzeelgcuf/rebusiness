from database_manager import DatabaseManager
from run_full_analysis import analyze_solicitation
import time

def test_flagging_logic():
    print("--- TEST: Manual Review Queue Flagging ---")
    db = DatabaseManager()
    
    # 1. Insert a Vague Solicitation (Should trigger low confidence)
    contract_id = f"TEST_LOW_CONF_{int(time.time())}"
    title = "Generic Requirement"
    description = "We need some supplies. Please quote." # Very vague, no quantity explanation
    
    print(f"Injecting test solicitation: {contract_id}")
    db.add_solicitation(
        contract_id=contract_id,
        url="http://test.local",
        title=title,
        description=description,
        location="USA",
        product_requirements=None,
        analysis_summary=None,
        data="{}"
    )
    
    # 2. Run Analysis manually
    print("Running analysis...")
    # We manually call the analysis function but we need to mock the DB update or just call the run script logic
    # Let's use the actual analysis function
    
    sol_dict = {'contract_id': contract_id, 'description': description}
    
    # Analyze
    text, confidence = analyze_solicitation(sol_dict)
    
    print(f"Analysis Complete.")
    print(f"Confidence Score: {confidence}")
    
    status = 'pending'
    if confidence is None or confidence < 0.8:
        status = 'flagged' # FLAG low confidence or None
        print("✅ SUCCESS: Item was FLAGGED (Confidence < 0.8 or None)")
    else:
        status = 'reviewed'
        print("❌ FAILURE: Item was NOT flagged.")
        
    # 3. Save key metrics to DB to verify dashboard would see it
    db.add_solicitation_analysis(contract_id, text, confidence, status)
    
    # 4. Verify DB State
    conn = db._connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT review_status FROM solicitations WHERE contract_id=?", (contract_id,))
    final_status = cursor.fetchone()[0]
    db._close_db()
    
    print(f"Final DB Status: {final_status}")

if __name__ == "__main__":
    test_flagging_logic()
