"""
Enhanced RFQ Quality Validation System
Ensures 100% compliance with Claude Vendor List.odt and Claude Service List.odt templates
"""
import os
import re
import sys
import docx
from typing import Dict, List, Tuple
from datetime import datetime

class RFQValidator:
    """
    Comprehensive validation system for RFQ output quality.
    Scoring: 0-100 points across multiple categories.
    """
    
    def __init__(self, template_type: str):
        self.template_type = template_type.upper()
        
        # Template-specific requirements
        self.required_sections = {
            'PRODUCT': [
                'Overview', 'Items Required', 'CLIN', 'Inspection',
                'Delivery Requirements', 'Data & Access', 'Submission Details',
                'Summary of What They Require', 'Key Takeaways'
            ],
            'SERVICE': [
                'In Summary', 'Summary of Project', 'What They Want',
                'Timeline', 'Deliverables', 'Work Locations',
                'Key Compliance', 'Acceptance Criteria', 'General Overview',
                'Key Requirements', 'Bid Submission Instructions',
                'Base Contract Scope', 'Key Takeaways for Bidder'
            ]
        }
        
        self.placeholder_phrases = [
            'not specified', 'n/a', 'see solicitation',
            'information not provided', 'details not provided',
            'not available', 'contact co', 'to be determined'
        ]
        
        # Scoring weights
        self.weights = {
            'content_completeness': 40,
            'contact_accuracy': 30,
            'format_compliance': 20,
            'technical_quality': 10
        }
    
    def validate_from_docx(self, docx_path: str) -> Dict:
        """
        Primary validation method from DOCX file.
        Returns detailed scoring report.
        """
        try:
            doc = docx.Document(docx_path)
            text = '\n'.join([p.text for p in doc.paragraphs])
            tables = doc.tables
        except Exception as e:
            return {
                'score': 0,
                'status': 'FAIL',
                'error': f"Cannot open DOCX: {e}",
                'issues': [],
                'details': {}
            }
        
        return self._validate_content(text, tables, docx_path)
    
    def validate_from_markdown(self, markdown_content: str) -> Dict:
        """
        Validate RFQ from markdown string (before conversion).
        """
        return self._validate_content(markdown_content, [], None)
    
    def _validate_content(
        self,
        text: str,
        tables: List,
        file_path: str = None
    ) -> Dict:
        """Core validation logic."""
        
        score = 0
        issues = []
        details = {}
        
        # ========== CATEGORY 1: CONTENT COMPLETENESS (40 pts) ==========
        
        # 1.1 Length check (10 pts)
        content_length = len(text)
        if content_length > 3000:
            score += 10
            details['content_length'] = f"✓ {content_length} chars"
        else:
            issues.append(f"Content too short ({content_length} chars, need >3000)")
            details['content_length'] = f"✗ {content_length} chars"
        
        # 1.2 Required sections (20 pts)
        required = self.required_sections.get(self.template_type, [])
        sections_present = sum(1 for section in required if section.lower() in text.lower())
        section_score = int((sections_present / len(required)) * 20)
        score += section_score
        details['sections'] = f"{sections_present}/{len(required)} present"
        
        if section_score < 15:
            missing = [s for s in required if s.lower() not in text.lower()]
            issues.append(f"Missing sections: {', '.join(missing[:3])}")
        
        # 1.3 Placeholder content check (10 pts)
        placeholder_count = sum(text.lower().count(p) for p in self.placeholder_phrases)
        if placeholder_count <= 3:
            score += 10
            details['placeholders'] = f"✓ {placeholder_count} found"
        else:
            issues.append(f"Too many placeholders ({placeholder_count} instances)")
            details['placeholders'] = f"✗ {placeholder_count} found"
        
        # ========== CATEGORY 2: CONTACT & DEADLINE ACCURACY (30 pts) ==========
        
        # 2.1 Camp Sable email (15 pts)
        if 'john@campsable.com' in text:
            score += 15
            details['camp_sable_email'] = "✓ Present"
        else:
            issues.append("Missing Camp Sable email")
            details['camp_sable_email'] = "✗ Missing"
        
        # 2.2 No government emails (15 pts)
        gov_email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:gov|mil)\b'
        gov_emails = re.findall(gov_email_pattern, text, re.IGNORECASE)
        # Filter out false positives (john@campsable.com shouldn't match)
        gov_emails = [e for e in gov_emails if 'campsable' not in e.lower()]
        
        if not gov_emails:
            score += 15
            details['gov_emails'] = "✓ None found"
        else:
            issues.append(f"Government emails found: {', '.join(gov_emails[:3])}")
            details['gov_emails'] = f"✗ {len(gov_emails)} found"
        
        # ========== CATEGORY 3: FORMAT COMPLIANCE (20 pts) ==========
        
        # 3.1 No bold formatting (10 pts)
        if '**' not in text:
            score += 10
            details['bold_formatting'] = "✓ None"
        else:
            bold_count = text.count('**') // 2
            issues.append(f"Bold formatting found ({bold_count} instances)")
            details['bold_formatting'] = f"✗ {bold_count} instances"
        
        # 3.2 Emoji headers (5 pts)
        if '🏛️' in text or '🟩' in text:
            score += 5
            details['emoji_headers'] = "✓ Present"
        else:
            issues.append("Missing emoji section headers")
            details['emoji_headers'] = "✗ Missing"
        
        # 3.3 Tables present (5 pts)
        if tables:
            score += 5
            details['tables'] = f"✓ {len(tables)} tables"
        elif '|' in text and text.count('|') > 10:
            score += 5
            details['tables'] = "✓ Markdown tables"
        else:
            issues.append("No properly formatted tables")
            details['tables'] = "✗ Missing"
        
        # ========== CATEGORY 4: TECHNICAL QUALITY (10 pts) ==========
        
        # 4.1 File size (if available)
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > 15000:
                score += 3
                details['file_size'] = f"✓ {file_size:,} bytes"
            else:
                issues.append(f"File size too small ({file_size:,} bytes)")
                details['file_size'] = f"✗ {file_size:,} bytes"
        else:
            score += 3  # Give benefit of doubt for markdown
            details['file_size'] = "N/A (markdown)"
        
        # 4.2 No HTML artifacts (3 pts)
        html_artifacts = ['<!--', '-->', '<div>', '</div>', '<p>', '</p>']
        html_found = [h for h in html_artifacts if h in text]
        
        if not html_found:
            score += 3
            details['html_artifacts'] = "✓ None"
        else:
            issues.append(f"HTML artifacts: {', '.join(set(html_found))}")
            details['html_artifacts'] = f"✗ {len(html_found)} types"
        
        # 4.3 Proper date formatting (2 pts)
        date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b'
        dates_found = re.findall(date_pattern, text)
        
        if dates_found:
            score += 2
            details['date_formatting'] = f"✓ {len(dates_found)} dates"
        else:
            issues.append("No properly formatted dates")
            details['date_formatting'] = "✗ None"
        
        # 4.4 Proper CLIN/table structure (2 pts)
        if self.template_type == 'PRODUCT':
            if 'CLIN' in text and '|' in text:
                score += 2
                details['clin_table'] = "✓ Present"
            else:
                issues.append("CLIN table missing or malformed")
                details['clin_table'] = "✗ Missing"
        else:  # SERVICE
            if 'Year 1' in text or 'Base Contract Scope' in text:
                score += 2
                details['service_structure'] = "✓ Present"
            else:
                issues.append("Service timeline/scope structure missing")
                details['service_structure'] = "✗ Missing"
        
        # ========== FINAL SCORING ==========
        
        # Determine status
        if score >= 95:
            status = "✅ PASS"
        elif score >= 80:
            status = "⚠️ NEEDS IMPROVEMENT"
        else:
            status = "❌ FAIL"
        
        return {
            'score': score,
            'status': status,
            'issues': issues,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_report(self, validation_result: Dict, output_path: str = None):
        """Generate detailed validation report."""
        
        report = f"""
{'='*60}
RFQ QUALITY VALIDATION REPORT
{'='*60}
Type: {self.template_type}
Date: {validation_result.get('timestamp', 'N/A')}
{'='*60}

SCORE: {validation_result['score']}/100
Status: {validation_result['status']}

{'='*60}
DETAILS:
{'='*60}
"""
        for key, value in validation_result['details'].items():
            report += f"  {key:.<30} {value}\n"
        
        if validation_result['issues']:
            report += f"\n{'='*60}\n"
            report += f"ISSUES FOUND ({len(validation_result['issues'])}):\n"
            report += f"{'='*60}\n"
            for i, issue in enumerate(validation_result['issues'], 1):
                report += f"  {i}. {issue}\n"
        
        report += f"\n{'='*60}\n"
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
        
        return report


class TemplateComplianceChecker:
    """
    Advanced checker for exact template compliance.
    Compares structure, content patterns, and formatting.
    """
    
    def __init__(self):
        # Define critical patterns that MUST appear
        self.critical_patterns = {
            'PRODUCT': [
                r'Notice ID:',
                r'Dear \[Vendor\]:',
                r'john@campsable\.com',
                r'## 🏛️ Overview',
                r'## 🏛️ Items Required',
                r'## 🏛️ Delivery Requirements',
                r'## 🟩 Summary of What They Require',
                r'## 🟩 Key Takeaways'
            ],
            'SERVICE': [
                r'Notice ID:',
                r'Dear \[Vendor\]:',
                r'john@campsable\.com',
                r'## 🟩 In Summary',
                r'## 🏛️ Summary of Project',
                r'## 🏛️ What They Want',
                r'## 🏛️ Timeline',
                r'## 🟩 Key Takeaways for Bidder',
                r'- \[ \]'  # Checkbox format for service
            ]
        }
    
    def check_compliance(self, rfq_content: str, rfq_type: str) -> Dict:
        """
        Check if RFQ matches template structure exactly.
        Returns compliance score and specific violations.
        """
        patterns = self.critical_patterns.get(rfq_type, [])
        violations = []
        matches = 0
        
        for pattern in patterns:
            if re.search(pattern, rfq_content):
                matches += 1
            else:
                violations.append(f"Missing pattern: {pattern}")
        
        compliance_score = (matches / len(patterns)) * 100 if patterns else 0
        
        # Additional checks
        if rfq_type == 'SERVICE':
            # Check for checklist format
            checkbox_count = rfq_content.count('- [ ]')
            if checkbox_count < 10:
                violations.append(f"SERVICE RFQ should have >=10 checkboxes, found {checkbox_count}")
        
        return {
            'compliance_score': compliance_score,
            'matches': matches,
            'total_patterns': len(patterns),
            'violations': violations,
            'is_compliant': compliance_score >= 95
        }


def validate_rfq_cli():
    """CLI interface for validation."""
    if len(sys.argv) < 3:
        print("Usage: python validate_rfq.py <docx_path> <PRODUCT|SERVICE>")
        sys.exit(1)
    
    docx_path = sys.argv[1]
    template_type = sys.argv[2].upper()
    
    if not os.path.exists(docx_path):
        print(f"Error: File not found: {docx_path}")
        sys.exit(1)
    
    if template_type not in ['PRODUCT', 'SERVICE']:
        print(f"Error: Type must be PRODUCT or SERVICE, got: {template_type}")
        sys.exit(1)
    
    # Run validation
    validator = RFQValidator(template_type)
    result = validator.validate_from_docx(docx_path)
    
    # Generate report
    report = validator.generate_report(result)
    print(report)
    
    # Template compliance check
    checker = TemplateComplianceChecker()
    doc = docx.Document(docx_path)
    text = '\n'.join([p.text for p in doc.paragraphs])
    compliance = checker.check_compliance(text, template_type)
    
    print(f"\nTEMPLATE COMPLIANCE: {compliance['compliance_score']:.1f}%")
    if compliance['violations']:
        print("\nVIOLATIONS:")
        for v in compliance['violations']:
            print(f"  - {v}")
    
    # Exit code
    sys.exit(0 if result['score'] >= 95 and compliance['is_compliant'] else 1)


if __name__ == "__main__":
    validate_rfq_cli()
