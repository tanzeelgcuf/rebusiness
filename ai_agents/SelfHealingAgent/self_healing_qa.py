"""
Self-Healing Quality Assurance Agent
Validates RFQ output against reference templates and triggers re-extraction
"""
import os
import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class SelfHealingQAAgent:
    """
    Validates generated RFQ against reference templates.
    Identifies missing information and triggers intelligent re-extraction.
    """
    
    def __init__(self, config):
        self.config = config
        
        # Reference template paths
        self.product_template_path = "reference_templates/Claude Vendor List.odt"
        self.service_template_path = "reference_templates/Claude Service List.odt"
        
        # Load reference template structures
        self.product_template_structure = self._load_template_structure("PRODUCT")
        self.service_template_structure = self._load_template_structure("SERVICE")
    
    def _load_template_structure(self, rfq_type: str) -> Dict:
        """
        Extract expected structure from reference templates.
        Returns dict of required fields and their patterns.
        """
        if rfq_type == "PRODUCT":
            return {
                'required_sections': [
                    'Overview',
                    'Items Required',
                    'CLIN Table',
                    'Inspection & Testing',
                    'Delivery Requirements',
                    'Data & Access Requirements',
                    'REQUIRED CERTIFICATIONS',
                    'Submission Details',
                    'Delivery Summary Table',
                    'Summary of What They Require',
                    'Key Takeaways for Bidders'
                ],
                'required_fields': {
                    'agency_address': {
                        'pattern': r'Agency Issuing RFQ:\s*\n([^\n]+)\s*\n([^\n]+)\s*\n([^\n]+)',
                        'expected_lines': 3,  # Name, Street, City/State/Zip
                        'example': 'Defense Logistics Agency\n6501 East Eleven Mile Road\nWarren, MI 48397'
                    },
                    'notice_id': {
                        'pattern': r'Notice ID[:\s]+([A-Z0-9\-]+)',
                        'must_not_contain': ['[', ']', '{', '}', 'Extract', 'solicitation_number']
                    },
                    'naics': {
                        'pattern': r'NAICS Code[:\s]+(\d{6})\s*--\s*([^\n]+)',
                        'must_have': ['6-digit code', 'description']
                    },
                    'delivery_address': {
                        'pattern': r'Destination: Ship to\s+([^\n]+(?:\n[^\n]+){2,4})',
                        'expected_components': ['street', 'city', 'state', 'zip'],
                        'must_not_be': ['[Facility_Name_if_applicable]', '[Complete_Street_Address]']
                    },
                    'contract_duration': {
                        'pattern': r'This is a (\d+)-year\s+(\w+)\s+contract',
                        'must_not_contain': ['[X]', '[Y]', 'indefinite quantity or requirements']
                    },
                    'systems_required': {
                        'context': 'Systems required:',
                        'must_not_be': ['[List_all - WAWF, PIEE, WIMS, etc.]'],
                        'expected_format': 'Comma-separated list of actual systems'
                    },
                    'documentation_requirements': {
                        'context': 'Documentation:',
                        'must_not_be': ['[Specific_requirements - traceability, test reports, etc.]']
                    },
                    'lead_time': {
                        'pattern': r'Lead time[:\s]+(\d+\s+(?:days|weeks|months))',
                        'must_not_contain': ['To be determined', 'Per Schedule of Supplies']
                    }
                },
                'forbidden_patterns': [
                    r'\[Extract[^\]]*\]',
                    r'\{[^\}]+\}',
                    r'EXTRACTION LOGIC',
                    r'Must Extract:',
                    r'\[Facility_Name_if_applicable\]',
                    r'\[Complete_Street_Address\]',
                    r'\[X\]-year',
                    r'\[List_all[^\]]*\]',
                    r'\[Specific_[^\]]*\]'
                ]
            }
        else:  # SERVICE
            return {
                'required_sections': [
                    'In Summary',
                    'Summary of Project',
                    'What They Want',
                    'Timeline / Period of Performance',
                    'Deliverables & Reporting Deadlines',
                    'Delivery / Work Locations',
                    'Key Compliance Points',
                    'Acceptance Criteria',
                    'General Overview',
                    'Key Requirements',
                    'Bid Submission Instructions',
                    'Base Contract Scope',
                    'ATTACHMENTS PROVIDED',
                    'Summary for Bidders',
                    'Key Takeaways for Bidder'
                ],
                'required_fields': {
                    'in_summary': {
                        'bullets': 3,
                        'must_contain': ['They want:', 'Time frame:', 'Delivery locations:']
                    },
                    'work_locations': {
                        'must_have': ['Site names', 'Addresses or descriptions', 'State/County'],
                        'must_not_be': ['Not specified', 'Various sites']
                    },
                    'wage_determination': {
                        'pattern': r'Wage Determination[:\s]+(WD\s*\d+[-\d]*|[\d\-]+)',
                        'must_not_be': ['Not specified', 'TBD']
                    },
                    'key_takeaways_format': {
                        'must_use': '- [ ]',
                        'must_not_use': ['1.', '2.', 'regular bullets']
                    }
                },
                'forbidden_patterns': [
                    r'See PWS',
                    r'As per solicitation',
                    r'\[Extract[^\]]*\]',
                    r'EXTRACTION LOGIC'
                ]
            }
    
    def validate_rfq(self, rfq_content: str, rfq_type: str) -> Tuple[bool, List[str], Dict]:
        """
        Comprehensive validation against reference template.
        
        Returns:
            (is_valid, list_of_issues, missing_fields_dict)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"SELF-HEALING QA: Validating {rfq_type} RFQ")
        logger.info(f"{'='*80}\n")
        
        issues = []
        missing_fields = {}
        
        template = self.product_template_structure if rfq_type == "PRODUCT" else self.service_template_structure
        
        # 1. Check for forbidden patterns (instruction leakage)
        logger.info("  [1/5] Checking for instruction leakage...")
        for pattern in template['forbidden_patterns']:
            matches = re.findall(pattern, rfq_content, re.IGNORECASE)
            if matches:
                issues.append(f"CRITICAL: Instruction leakage found: {matches[:3]}")
                logger.error(f"    ✗ Found: {pattern} → {matches[:3]}")
        
        # 2. Check required sections
        logger.info("  [2/5] Verifying required sections...")
        missing_sections = []
        for section in template['required_sections']:
            if section.lower() not in rfq_content.lower():
                missing_sections.append(section)
                issues.append(f"Missing section: {section}")
        
        if missing_sections:
            logger.warning(f"    Missing {len(missing_sections)} sections: {missing_sections}")
        else:
            logger.info("    ✓ All sections present")
        
        # 3. Validate required fields
        logger.info("  [3/5] Validating critical fields...")
        for field_name, field_spec in template['required_fields'].items():
            field_valid, field_issues = self._validate_field(rfq_content, field_name, field_spec)
            
            if not field_valid:
                issues.extend(field_issues)
                missing_fields[field_name] = field_spec
                logger.error(f"    ✗ {field_name}: {field_issues[0]}")
            else:
                logger.info(f"    ✓ {field_name}: Valid")
        
        # 4. Check for placeholder text
        logger.info("  [4/5] Scanning for placeholder text...")
        placeholder_patterns = [
            r'\[(?!My signature info\])[^\]]+\]',  # Brackets except [My signature info]
            r'Not specified in solicitation documents',
            r'Details not provided'
        ]
        
        placeholder_count = 0
        for pattern in placeholder_patterns:
            matches = re.findall(pattern, rfq_content)
            placeholder_count += len(matches)
        
        if placeholder_count > 2:  # Allow max 2 "Not specified"
            issues.append(f"CRITICAL: Too many placeholders ({placeholder_count}), limit is 2")
            logger.error(f"    ✗ Found {placeholder_count} placeholders (limit: 2)")
        else:
            logger.info(f"    ✓ Placeholder count acceptable ({placeholder_count})")
        
        # 5. Validate formatting
        logger.info("  [5/5] Checking formatting...")
        if '**' in rfq_content:
            issues.append("Bold formatting (**) found - should be removed")
            logger.warning("    ✗ Bold formatting present")
        
        if re.search(r'[\w\.-]+@[\w\.-]*\.(?:gov|mil)\b', rfq_content):
            issues.append("Government emails found - should be replaced with bobbysmitty078@gmail.com")
            logger.warning("    ✗ Government emails present")
        
        # Final verdict
        is_valid = len(issues) == 0
        
        logger.info(f"\n{'='*80}")
        if is_valid:
            logger.info("✓ VALIDATION PASSED")
        else:
            logger.error(f"✗ VALIDATION FAILED: {len(issues)} issues found")
        logger.info(f"{'='*80}\n")
        
        return is_valid, issues, missing_fields
    
    def _validate_field(self, content: str, field_name: str, field_spec: Dict) -> Tuple[bool, List[str]]:
        """Validate a specific field according to its specification."""
        issues = []
        
        # Check pattern match if specified
        if 'pattern' in field_spec:
            match = re.search(field_spec['pattern'], content, re.IGNORECASE | re.MULTILINE)
            if not match:
                issues.append(f"{field_name}: Pattern not found or incomplete")
                return False, issues
        
        # Check must_not_contain
        if 'must_not_contain' in field_spec:
            for forbidden in field_spec['must_not_contain']:
                if forbidden in content:
                    issues.append(f"{field_name}: Contains forbidden text '{forbidden}'")
                    return False, issues
        
        # Check must_not_be
        if 'must_not_be' in field_spec:
            for forbidden in field_spec['must_not_be']:
                if forbidden in content:
                    issues.append(f"{field_name}: Exact forbidden value found '{forbidden}'")
                    return False, issues
        
        # Check expected_components
        if 'expected_components' in field_spec:
            # Extract context around field
            context_pattern = field_spec.get('pattern', field_spec.get('context', ''))
            if context_pattern:
                match = re.search(context_pattern, content, re.IGNORECASE | re.MULTILINE)
                if match:
                    field_content = match.group(0)
                    missing_components = []
                    
                    for component in field_spec['expected_components']:
                        # Very basic check - can be enhanced
                        if not re.search(r'\d{5}', field_content) and component == 'zip':
                            missing_components.append(component)
                    
                    if missing_components:
                        issues.append(f"{field_name}: Missing components: {missing_components}")
                        return False, issues
        
        return True, []
    
    def generate_improvement_instructions(
        self, 
        missing_fields: Dict,
        rfq_type: str
    ) -> str:
        """
        Generate SIMPLIFIED, DIRECTIVE instructions for re-extraction.
        CRITICAL: Keep instructions short to prevent instruction leakage.
        
        Returns:
            Brief, directive prompt for LLM to fix issues
        """
        # Build list of specific fixes needed
        fixes_needed = []
        
        for field_name in missing_fields.keys():
            if field_name == 'agency_address':
                fixes_needed.append("Extract complete agency address (3 lines: name, street, city/state/zip)")
            elif field_name == 'notice_id':
                fixes_needed.append("Extract notice ID without brackets or placeholders")
            elif field_name == 'delivery_address':
                fixes_needed.append("Extract complete delivery address with street, city, state, zip")
            elif field_name == 'contract_duration':
                fixes_needed.append("Extract specific contract duration (e.g., '5-year') - no [X] placeholders")
            elif field_name == 'systems_required':
                fixes_needed.append("List actual systems required (e.g., WAWF, SAM.gov) - no generic placeholders")
            elif field_name == 'lead_time':
                fixes_needed.append("Extract specific lead time (e.g., '120 days ARO') - no vague references")
            elif field_name == 'work_locations':
                fixes_needed.append("Extract specific work site names and addresses - no 'Not specified'")
            elif field_name == 'wage_determination':
                fixes_needed.append("Extract wage determination number (e.g., WD 2015-1234) - no 'Not specified'")
            else:
                fixes_needed.append(f"Extract complete {field_name.replace('_', ' ')}")
        
        # Create short, directive instruction
        instructions = f"""CRITICAL CORRECTIONS NEEDED:

The following fields are missing or incomplete. Re-generate the RFQ with these fixes:

{chr(10).join(f"{i+1}. {fix}" for i, fix in enumerate(fixes_needed))}

RULES:
- Extract ACTUAL values from the solicitation documents
- NO placeholders in [brackets] except [My signature info]
- NO instruction text like "EXTRACTION LOGIC" or "Must Extract:"
- NO "Not specified" unless truly unavailable after checking all documents
- Output ONLY the final RFQ content

Re-generate the complete RFQ with these corrections applied."""
        
        return instructions


# ==================== INTEGRATION FUNCTION ====================

def self_healing_rfq_generation(
    attachment_reader_agent,
    contract_id: str,
    max_iterations: int = 3
) -> Dict:
    """
    Self-healing RFQ generation with automatic quality checking and re-extraction.
    
    Args:
        attachment_reader_agent: Instance of AttachmentReaderAgent
        contract_id: Contract ID to process
        max_iterations: Maximum re-extraction attempts
    
    Returns:
        Final result dict with RFQ content and validation status
    """
    logger.info(f"\n{'='*100}")
    logger.info(f"SELF-HEALING RFQ GENERATION: {contract_id}")
    logger.info(f"{'='*100}\n")
    
    qa_agent = SelfHealingQAAgent(attachment_reader_agent.config)
    
    iteration = 0
    result = None
    
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"\n{'='*80}")
        logger.info(f"ITERATION {iteration}/{max_iterations}")
        logger.info(f"{'='*80}\n")
        
        # Generate or re-generate RFQ
        if iteration == 1:
            # First generation
            result = attachment_reader_agent.create_summary_report(
                contract_id,
                skip_json=True,
                strict_fidelity=True
            )
        else:
            # Re-generation with targeted instructions
            # This would require modifying the attachment_reader_agent
            # to accept custom instructions
            logger.warning("Re-extraction not yet implemented in this version")
            break
        
        if "error" in result:
            logger.error(f"Generation failed: {result['error']}")
            break
        
        # Validate generated RFQ
        is_valid, issues, missing_fields = qa_agent.validate_rfq(
            result['rfq_content'],
            result['rfq_type']
        )
        
        if is_valid:
            logger.info(f"\n{'='*80}")
            logger.info(f"✓ RFQ VALID - Self-healing complete in {iteration} iteration(s)")
            logger.info(f"{'='*80}\n")
            break
        else:
            logger.warning(f"\n{'='*80}")
            logger.warning(f"✗ Iteration {iteration} failed validation")
            logger.warning(f"Issues: {len(issues)}")
            for issue in issues[:5]:
                logger.warning(f"  - {issue}")
            logger.warning(f"{'='*80}\n")
            
            if iteration >= max_iterations:
                logger.error(f"Maximum iterations reached. RFQ may be incomplete.")
                result['validation_warning'] = f"Failed validation after {max_iterations} attempts"
                result['issues'] = issues
    
    return result
