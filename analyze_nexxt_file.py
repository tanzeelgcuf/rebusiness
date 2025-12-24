
import sys
import os
import asyncio
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents')))
from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

FILE_PATH = "/Users/apple/Downloads/rebusinessautomationproject/data/solicitations/483f26d1ad/attachments/36C26126P0265_1.docx"

def main():
    print(f"Analyzing file: {FILE_PATH}")
    agent = AttachmentReaderAgent()
    
    # We use the _analyze_content_with_llm or just create_summary_report if we had the ID, 
    # but here we want to force read specific file
    content = agent._read_file_content(FILE_PATH)
    if not content:
        print("Failed to read file.")
        return

    # Mock full sol_data structure for the agent
    sol_data = {
        "contract_id": "483f26d1ad",
        "title": "Nexxt Spine Investigation",
        "description": "Deep dive extraction",
        "attachments": [FILE_PATH]
    }
    
    # We actually need to call _analyze_content_with_llm directly or mimic process_solicitation.
    # Let's use the public analyze_files method if available? No, let's use internal helper for speed.
    # Actually, create_summary_report iterates all files in the directory.
    
    print("Running full directory analysis...")
    summary = agent.create_summary_report("483f26d1ad")
    print("\n--- ANALYSIS OUTPUT ---")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
