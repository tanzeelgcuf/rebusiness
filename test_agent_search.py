from ai_agents.ThomasNetAgent.thomasnet_agent import ThomasNetAgent
from database_manager import DatabaseManager

db = DatabaseManager()
agent = ThomasNetAgent()

# Test the search engine method
product = {'product_name': 'Industrial Bolts'}
suppliers = agent.find_suppliers_for_product(product)

print(f"Found {len(suppliers)} suppliers via Search.")
for s in suppliers:
    print(s)
    agent.save_supplier(s)
