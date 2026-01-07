
import json
import sys
import os

# Ensure we can import the agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/ProposalWriterAgent')))
from proposal_writer import create_bid_request

def test_v8_formatting():
    # Load v8 analysis
    with open('W912ES26BA007_analysis_v8.json', 'r') as f:
        data = json.load(f)
    
    # Generate Output
    output = create_bid_request(data)
    
    # Save
    with open('W912ES26BA007_verify_output_v8_reformat.txt', 'w') as f:
        f.write(output['body'])
        
    print("Generated W912ES26BA007_verify_output_v8_reformat.txt")

if __name__ == "__main__":
    test_v8_formatting()
