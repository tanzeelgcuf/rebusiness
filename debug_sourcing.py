from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent

def test_sourcing(product_name):
    print(f"\n--- Testing Product: {product_name} ---")
    agent = ThomasNetAgent()
    
    # 1. Run the search
    suppliers = agent.find_suppliers_for_product({'product_name': product_name})
    
    print(f"\nFound {len(suppliers)} suppliers:")
    for s in suppliers:
        print(f"Name: {s['name']}")
        print(f"Web:  {s['website']}")
        print(f"Note: {s.get('notes')}")
        print("-" * 20)

if __name__ == "__main__":
    test_sourcing("Savit D1-EOD Kit Components")
    test_sourcing("Industrial Bolts")
