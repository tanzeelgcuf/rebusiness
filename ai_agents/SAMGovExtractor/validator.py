
"""
Strict validation logic for SAM.gov extraction.
"""

import re
from typing import Dict, List, Tuple

class SolicitationValidator:
    """Validates extracted solicitation data against strict quality rules."""

    FORBIDDEN_PHRASES = [
        "as per solicitation",
        "see sam.gov",
        "as specified",
        "refer to attachment",
        "not provided",
        "tbd",
        "unknown"
    ]

    DATE_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}(T.*)?$') # ISO Format preferred
    # Also allow specific relative terms if very clear
    RELATIVE_DATE_REGEX = re.compile(r'\d+\s+(days|weeks|months)\s+aro', re.IGNORECASE)

    @staticmethod
    def validate(data: Dict) -> Tuple[bool, List[str]]:
        """
        Validates the dictionary of extracted data based on its category.
        """
        errors = []
        category = data.get('solicitation_category', 'Product')

        # 1. Critical common fields
        if not data.get('notice_id') or SolicitationValidator._contains_placeholder(str(data.get('notice_id'))):
             errors.append("Invalid or missing Notice ID")
        if not data.get('title') or SolicitationValidator._contains_placeholder(str(data.get('title'))):
             errors.append("Invalid or missing Title")

        # 2. Category-specific validation
        if category == "Product":
            # Overview check
            ov = data.get('overview', {})
            due_date = ov.get('quotes_due_date')
            if not due_date or not SolicitationValidator._is_valid_date(str(due_date)):
                 errors.append(f"Invalid or missing Due Date (Product/Overview): '{due_date}'")
            
            # CLINs
            clins = data.get('clins')
            if not clins or not isinstance(clins, list) or len(clins) == 0:
                 errors.append("No Product CLINs extracted")
            
            # Delivery
            deliv = data.get('delivery_requirements', {})
            addr = deliv.get('ship_to_address')
            if not addr or len(str(addr)) < 10 or SolicitationValidator._contains_placeholder(str(addr)):
                 errors.append("Invalid or missing Product Ship-To Address")
            
            sched = deliv.get('schedule_aro')
            if not sched or SolicitationValidator._contains_placeholder(str(sched)):
                 errors.append("Invalid or missing Product Delivery Schedule (ARO)")

        else: # Service
            # Submission Instructions check
            si = data.get('submission_instructions', {})
            due_date = si.get('official_deadline')
            if not due_date or not SolicitationValidator._is_valid_date(str(due_date)):
                 errors.append(f"Invalid or missing Due Date (Service/Submission): '{due_date}'")
            
            # CLINs breakdown
            clins = data.get('clins_breakdown')
            if not clins or not isinstance(clins, list) or len(clins) == 0:
                 errors.append("No Service CLINs breakdown extracted")
            
            # Key Requirements / Insurance
            reqs = data.get('key_requirements', {})
            ins = reqs.get('insurance_requirements')
            if not ins or not isinstance(ins, dict) or len(ins) < 2:
                 errors.append("Missing or incomplete Service Insurance requirements")

        return (len(errors) == 0), errors

    @staticmethod
    def _contains_placeholder(text: str) -> bool:
        """Checks if text contains forbidden placeholder phrases."""
        if not text: return False
        lower_text = text.lower().strip()
        
        # Check explicit forbidden phrases
        for phrase in SolicitationValidator.FORBIDDEN_PHRASES:
            if phrase in lower_text:
                return True
        
        return False

    @staticmethod
    def _is_valid_date(text: str) -> bool:
        """Checks if text is a valid specific date or specific relative term."""
        if not text: return False
        
        # Check ISO format
        if SolicitationValidator.DATE_REGEX.match(text):
            return True
            
        # Check relative (e.g. "30 days ARO")
        if SolicitationValidator.RELATIVE_DATE_REGEX.search(text):
            return True
            
        # Check strict common formats
        try:
             # Just a basic check if we can parse it using generic logic (omitted here for regex speed)
             # logic: if it has digits and months, it's likely a date.
             # Fail if it's just "See Solicitation"
             if any(m in text.lower() for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                 if any(c.isdigit() for c in text):
                     return True
        except: pass

        return False
