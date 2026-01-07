import os
import re
import sys
import docx
from datetime import datetime

class RFQValidator:
    def __init__(self, file_path, rfq_type="PRODUCT"):
        self.file_path = file_path
        self.rfq_type = rfq_type.upper()
        self.score = 100
        self.report = []
        self.content = ""
        
    def log(self, points, message):
        self.score -= points
        self.report.append(f"[-{points}] {message}")

    def load_file(self):
        if not os.path.exists(self.file_path):
            self.log(100, "File not found")
            return False
            
        try:
            if self.file_path.endswith('.docx'):
                doc = docx.Document(self.file_path)
                self.content = "\n".join([p.text for p in doc.paragraphs])
            else:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.content = f.read()
            return True
        except Exception as e:
            self.log(100, f"Critical: Could not read file: {e}")
            return False

    def validate(self):
        if not self.load_file():
            return 0
            
        print(f"Validating: {os.path.basename(self.file_path)}")
        
        # 1. Format Check (30 pts)
        if "**" in self.content:
            count = self.content.count("**")
            self.log(20, f"Found {count} instances of markdown bold ('**'). STRICTLY PROHIBITED.")
            
        if "  " in self.content and "|" in self.content:
            # Check for bad markdown tables if it's md, but strict pipeline produces docx
            pass

        # 2. Contact Info (20 pts)
        if "john@campsable.com" not in self.content:
            self.log(20, "Missing required contact email: john@campsable.com")
            
        gov_domains = [".gov", ".mil", "navy.mil", "army.mil", "usace.army.mil"]
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, self.content)
        
        gov_emails_found = [e for e in emails if any(d in e for d in gov_domains)]
        if gov_emails_found:
             self.log(15, f"Found government emails (LEAKAGE): {gov_emails_found}")

        # 3. Content Completeness (30 pts)
        # 3. Content Completeness (30 pts)
        required_sections = []
        if self.rfq_type == "PRODUCT":
            required_sections = [
                "Overview",
                "Items Required",
                "Start Submission Details" # Changed lookup slightly to be robust
            ]
        else: # SERVICE
            required_sections = [
                "Summary of Project",
                "What They Want",
                "Bid Submission Instructions"
            ]

        # Checking for section headers
        # We perform a looser check because DOCX conversion might alter formatting
        # We check if the PHRASE exists in the content
        current_score_deduction = 0
        for section in required_sections:
            # Check for exact section headers or close variants
            found = False
            if section in self.content:
                found = True
            elif section == "Start Submission Details" and ("Submission Details" in self.content or "Submission Instructions" in self.content):
                found = True
            
            if not found:
                self.log(10, f"Missing required section: {section}")
                current_score_deduction += 10
                
        # 4. Placeholders (20 pts)
        placeholders = ["Information not provided", "See solicitation", "Insert Date", "[Date]", "[Name]"]
        for p in placeholders:
            if p.lower() in self.content.lower():
                self.log(5, f"Found placeholder text: '{p}'")

        return max(0, self.score)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to RFQ file (.docx or .md)")
    parser.add_argument("type", nargs='?', default="PRODUCT", help="RFQ Type: PRODUCT or SERVICE")
    args = parser.parse_args()
    
    validator = RFQValidator(args.file, args.type)
    final_score = validator.validate()
    
    print("\n" + "="*40)
    print(f"VALIDATION REPORT for {os.path.basename(args.file)}")
    print(f"FINAL SCORE: {final_score}/100")
    print("="*40)
    
    if validator.report:
        for item in validator.report:
            print(item)
    else:
        print("✓ PERFECT SCORE! No issues found.")
    
    if final_score < 95:
        sys.exit(1)
