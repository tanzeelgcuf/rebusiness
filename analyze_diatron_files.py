
import asyncio
import os
import sys
# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ai_agents.AttachmentReaderAgent.attachment_reader_agent import AttachmentReaderAgent

async def main():
    agent = AttachmentReaderAgent()
    
    files = [
        os.path.abspath("downloads/diatron_files/Hematology Attchment A 2026 12.10.2025 ILW.xlsx"),
        os.path.abspath("downloads/diatron_files/36C25526Q0105.docx")
    ]
    
    content_parts = []
    for f in files:
        if os.path.exists(f):
            print(f"Reading {f}...")
            # Using _read_file_content (which is synchronous and handles extensions)
            content = agent._read_file_content(f)
            if content:
                content_parts.append(f"--- File: {os.path.basename(f)} ---\n{content}")
            else:
                 print(f"Failed to read content from {f}")

    if content_parts:
        print("Analyzing with LLM...")
        # Direct call to analyze
        analysis = agent._analyze_content_with_llm(content_parts)
        import json
        print(json.dumps(analysis, indent=2))
    else:
        print("No content extracted.")

if __name__ == "__main__":
    asyncio.run(main())
