from duckduckgo_search import DDGS
import time

def test_ddg():
    print("Testing DDG Connectivity...")
    
    queries = [
        ("Simple", "test"),
        ("Thomasnet", "Thomasnet Industrial Bolts suppliers"),
        ("Site Operator", "site:thomasnet.com Industrial Bolts")
    ]
    
    for label, q in queries:
        print(f"\n--- {label} Query: '{q}' ---")
        try:
            results = DDGS().text(q, max_results=5)
            print(f"Count: {len(results)}")
            if results:
                print(f"First: {results[0]['title']}")
            else:
                print("No results.")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(2)

if __name__ == "__main__":
    test_ddg()
