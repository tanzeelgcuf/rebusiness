
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))

from SolicitationAnalysisAgent.solicitation_analysis import analyze_solicitation

# Mock solicitation data
mock_sol = {
    "contract_id": "test_123",
    "title": "Supply of Industrial Bolts",
    "description": "The Defense Logistics Agency requires 5000 units of heavy duty industrial non-corrosive hexagon bolts. Size: 5/8 inch. Material: Stainless Steel. NAICS: 332722."
}

print("Running Analysis Test...")
analysis, confidence = analyze_solicitation(mock_sol)

print(f"\nConfidence: {confidence}")
print(f"Analysis Output:\n{analysis}")
