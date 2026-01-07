
import os
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pdfplumber
from pathlib import Path


class VendorListOutputGenerator:
    """
    Generates vendor RFQ emails in the exact format of Claude Vendor List.odt
    Specifically for PRODUCT solicitations (not services)
    """
    
    def __init__(self):
        self.icon_summary = "🔹"
        self.icon_items = "🔹"
        self.icon_inspection = "🔹"
        self.icon_delivery = "🔹"
        self.icon_data = "🔹"
        self.icon_submission = "🔹"
        self.icon_insummary = "🟩"
        self.icon_tip = "✅"
        
    def generate_vendor_rfq(self, analysis: Dict) -> str:
        """
        Main method to generate complete RFQ email
        
        Args:
            analysis: Dictionary from AttachmentReaderAgent with all extracted data
            
        Returns:
            Formatted markdown string matching Claude Vendor List.odt
        """
        
        output = []
        
        # HEADER
        output.append(self._generate_header(analysis))
        
        # COVER LETTER
        output.append(self._generate_cover_letter(analysis))
        
        # IN SUMMARY
        output.append(self._generate_in_summary(analysis))
        
        # OVERVIEW
        output.append(self._generate_overview(analysis))
        
        # ITEMS REQUIRED
        output.append(self._generate_items_section(analysis))
        
        # INSPECTION & TESTING
        output.append(self._generate_inspection_section(analysis))
        
        # DELIVERY REQUIREMENTS
        output.append(self._generate_delivery_section(analysis))
        
        # DATA & ACCESS
        output.append(self._generate_data_access_section(analysis))
        
        # SUBMISSION DETAILS
        output.append(self._generate_submission_section(analysis))
        
        # DELIVERY SUMMARY TABLE
        output.append(self._generate_delivery_summary_table(analysis))
        
        # SUMMARY OF REQUIREMENTS
        output.append(self._generate_requirements_summary(analysis))
        
        # QUICK VENDOR TIP
        output.append(self._generate_vendor_tip())
        
        # CLOSING
        output.append(self._generate_closing())
        
        return "\n\n".join(output)
    
    def _generate_header(self, analysis: Dict) -> str:
        """Generate document header with Notice ID"""
        notice_id = analysis.get('notice_id', analysis.get('contract_id', 'UNKNOWN'))
        title = analysis.get('title', 'SOLICITATION')
        
        # NSN should be present if available/inferred
        specs = analysis.get('specifications', {})
        nsn = specs.get('nsn', 'N/A')
        
        return f"""Notice ID: {notice_id}

### [{title} (NSN: {nsn})]"""
    
    def _generate_cover_letter(self, analysis: Dict) -> str:
        """Generate personalized cover letter"""
        
        # Calculate internal deadline (4 business days before official)
        submission = analysis.get('submission', {})
        official_due = submission.get('due_date', '')
        
        internal_deadline = "TBD"
        if official_due:
            # Parse and subtract 4 business days
            try:
                # Assuming format like "2026-01-22" or "January 22, 2026"
                # This is simplified - production needs robust date parsing
                internal_deadline = "4 business days prior to official deadline"
            except:
                pass
        
        item_name = analysis.get('title', 'the requested items')
        
        return f"""Dear [Vendor]:

We are writing to request a formal quote for {item_name.lower()}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.

**Internal Deadline:** Please submit your quote to us by {internal_deadline} to allow time for review and submission preparation.

If you have any questions regarding this request or need additional information, please contact me at john@campsable.com. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

John Campbell
Procurement Manager
Campsable LLC"""
    
    def _generate_in_summary(self, analysis: Dict) -> str:
        """Generate high-level summary section with emojis"""
        item_name = analysis.get('title', 'the requested items')
        specs = analysis.get('specifications', {})
        qty = specs.get('quantity', 'See Schedule')
        
        delivery = analysis.get('delivery_requirements', {})
        lead_time = delivery.get('lead_time_days', 'TBD')
        ship_to = delivery.get('ship_to_address', {})
        
        location = "Destination"
        if isinstance(ship_to, dict):
            location = f"{ship_to.get('organization', 'Agency')} ({ship_to.get('city', '')}, {ship_to.get('state', '')})"
            
        return f"""## {self.icon_insummary} In Summary

**They want:** A qualified contractor to supply **{item_name.lower()}** ({qty} EA).
**Time frame:** Initial delivery starting {lead_time} days ARO.
**Delivery location:** {location}"""

    def _generate_overview(self, analysis: Dict) -> str:
        """Generate overview section matching template exactly"""
        
        overview = analysis.get('overview', {})
        specs = analysis.get('specifications', {})
        submission = analysis.get('submission', {})
        
        # Agency info with full address
        agency_name = overview.get('agency_name', 'Agency Name Not Specified')
        agency_addr = overview.get('agency_address', '')
        
        # Format address properly
        if isinstance(agency_addr, dict):
            addr_lines = [
                agency_addr.get('street', ''),
                f"{agency_addr.get('city', '')}, {agency_addr.get('state', '')} {agency_addr.get('zip', '')}"
            ]
            agency_address = '\n'.join([l for l in addr_lines if l.strip()])
        else:
            agency_address = str(agency_addr) if agency_addr else 'Address Not Specified'
        
        # Dates
        sol_date = overview.get('solicitation_date', 'See SAM.gov')
        due_date = submission.get('due_date', 'See SAM.gov')
        
        # Notice ID
        notice_id = analysis.get('notice_id', analysis.get('contract_id', 'N/A'))
        
        # Title with NSN
        title = analysis.get('title', 'Item Description')
        nsn = specs.get('nsn', 'N/A')
        if nsn and nsn != 'N/A':
            title_line = f"**Solicitation Title:** **{title} (NSN: {nsn})**"
        else:
            title_line = f"**Solicitation Title:** **{title}**"
        
        return f"""## {self.icon_summary} Overview

**Agency Issuing RFQ:**
{agency_name}
{agency_address}

**Type of Contract:** {overview.get('contract_type', 'Firm Fixed Price')}
**Set‑Aside Type:** {overview.get('set_aside', '100% Small Business Set‑Aside')}
**Solicitation Date:** {sol_date}
**Quotes Due:** {due_date}

{title_line}
**Contract Number (if awarded):** {notice_id}
**NAICS Code:** {overview.get('naics_code', 'N/A')} -- {overview.get('naics_description', 'See Solicitation')}
**Size Standard:** {overview.get('size_standard', 'See Solicitation')}"""
    
    def _generate_items_section(self, analysis: Dict) -> str:
        """Generate Items Required section with CLIN table"""
        
        specs = analysis.get('specifications', {})
        clins = analysis.get('clins', [])
        
        # Item header
        drawing = specs.get('drawing_number', specs.get('manufacturer_part_number', 'N/A'))
        cage = specs.get('manufacturer_cage', 'TBD at Award')
        part_num = specs.get('manufacturer_part_number', 'N/A')
        
        header = f"""## {self.icon_items} Items Required

### Item Requested: {analysis.get('title', 'Product Name')} per Top Drawing No. {drawing}

**Manufacturer CAGE:** {cage}
**Manufacturer Part Number:** {part_num}

**Description:** {specs.get('description', 'Standard item for military use (technical data package available via SAM.gov).')}"""
        
        # CLIN table
        if not clins:
            # Create a representative CLIN if none found, to match template style
            clins = [{
                'clin': '0001',
                'description': f"Base Year – {analysis.get('title', 'Item')}",
                'quantity': specs.get('quantity', '1'),
                'unit': 'EA',
                'type': 'FFP',
                'inspection_point': 'Origin',
                'quality_level': 'Military, Level B',
                'notes': 'Guaranteed Minimum Award Quantity'
            }]
        
        table_output = [header]
        table_output.append("\nEach production year is identified by a CLIN (Contract Line Item Number) with quantities and inspection requirements.\n")
        
        # CLIN Table Header
        table_output.append("| CLIN | Description | Quantity (EA) | Contract Type | Inspection/Acceptance | Packaging | Notes |")
        table_output.append("|---|---|---|---|---|---|---|")
        
        total_qty = 0
        min_qty = 0
        
        for idx, clin in enumerate(clins):
            clin_num = clin.get('clin', f"{idx+1:04d}")
            desc = clin.get('description', f"Year {idx+1}")
            qty = clin.get('quantity', 0)
            unit = clin.get('unit', 'EA')
            clin_type = clin.get('type', 'FFP')
            # Handle Inspection/Acceptance point
            insp = clin.get('inspection_point', 'Origin')
            acc = clin.get('acceptance_point', insp)
            insp_acc = f"{insp}/{acc}" if insp != acc else insp
            
            pkg = clin.get('packaging', specs.get('quality_level', 'Military, Level B'))
            notes = clin.get('notes', '')
            
            # Summing quantities for the total range
            try:
                q_val = int(re.sub(r'[^\d]', '', str(qty))) if any(c.isdigit() for c in str(qty)) else 0
            except:
                q_val = 0
            total_qty += q_val
            if idx == 0 or 'minimum' in notes.lower():
                min_qty = max(min_qty, q_val)
            
            table_output.append(f"| {clin_num} | {desc} | {qty} | {clin_type} | {insp_acc} | {pkg} | {notes} |")
        
        # Totals logic matching template
        if min_qty > 0:
            table_output.append(f"\n**Total Contract Quantity Range:**")
            table_output.append(f"- **Guaranteed Minimum Quantity:** {min_qty} Each")
            table_output.append(f"- **Maximum Contract Quantity:** {total_qty} Each")
        else:
            table_output.append(f"\n**Total Contract Quantity:** {total_qty} Each")
        
        # Packaging details matching template
        pkg_specs = specs.get('packaging_details', {})
        table_output.append(f"\n**Packaging:**")
        table_output.append(f"- MIL-STD-2073-1 compliant")
        table_output.append(f"- Preservation: {specs.get('preservation', 'Military, Level B')}")
        table_output.append(f"- Quantity per Unit: {specs.get('qty_per_unit', '1')}")
        if specs.get('spi_reference'):
            table_output.append(f"- SPI Reference: {specs['spi_reference']}")
        
        return "\n".join(table_output)
    
    def _generate_inspection_section(self, analysis: Dict) -> str:
        """Generate Inspection & Testing section"""
        
        quality = analysis.get('quality_requirements', {})
        
        insp_point = quality.get('inspection_point', 'Origin')
        accept_point = quality.get('acceptance_point', 'Origin')
        agency = quality.get('inspection_agency', 'DCMA (Defense Contract Management Agency)')
        
        output = [f"## {self.icon_inspection} Inspection & Testing"]
        
        output.append(f"""
- **Inspection Point:** {insp_point}
- **Acceptance Point:** {accept_point}
- **Inspection Agency:** {agency}
- **Requirement:** Notify inspection agency for inspection **before shipping**.
  - Failure to secure inspection will result in rejection at destination, and return at the contractor's expense.""")
        
        # IPI if mentioned
        if quality.get('initial_production_inspection'):
            output.append(f"""
**Initial Production Inspection (IPI):**
- Required -- {quality.get('ipi_sample_size', '3 units')} from the first production lot
- Verified by {quality.get('ipi_verifier', 'DCMA QAR')}
- Approval required before proceeding with full production""")
        
        # Quality standards
        qual_std = quality.get('quality_standard', 'ISO 9001:2015 or equivalent')
        output.append(f"\n**Quality Standard:** {qual_std}")
        
        return "\n".join(output)
    
    def _generate_delivery_section(self, analysis: Dict) -> str:
        """Generate Delivery Requirements section"""
        
        delivery = analysis.get('delivery_requirements', {})
        
        fob = delivery.get('fob_point', 'Destination')
        ship_to = delivery.get('ship_to_address', {})
        lead_time = delivery.get('lead_time_days', 'TBD')
        frequency = delivery.get('delivery_frequency', 'As specified in delivery order')
        
        # Format ship-to address
        if isinstance(ship_to, dict):
            ship_to_formatted = f"""- **Destination:** Ship to **{ship_to.get('organization', 'Agency')}**
  - {ship_to.get('street', '')}
  - {ship_to.get('city', '')}, {ship_to.get('state', '')} {ship_to.get('zip', '')}"""
        else:
            ship_to_formatted = f"- **Destination:** {ship_to}"
        
        output = [f"## {self.icon_delivery} Delivery Requirements"]
        
        output.append(f"""
### General Delivery Terms

- **FOB Point:** {fob}
{ship_to_formatted}
  - "Exact 'Ship‑To' instructions will be furnished with each delivery order."
- **Inspection:** {delivery.get('inspection_point', 'Origin')}
- **Acceptance:** {delivery.get('acceptance_point', 'Origin')}

### Delivery Schedule

- Delivery must begin **{lead_time} days ARO** (After Receipt of Order)
- **Deliveries:** {frequency}
- **Acceleration:** Early delivery accepted at no extra cost

**Definition:**
> "Days" means calendar days after date of delivery order issuance.

**Estimated Overall Duration:**
This is a **multi-year contract** with multiple annual ordering periods (if applicable).""")
        
        return "\n".join(output)
    
    def _generate_data_access_section(self, analysis: Dict) -> str:
        """Generate Data & Access Requirements section"""
        
        compliance = analysis.get('compliance', {})
        data_reqs = compliance.get('data_access', {})
        
        output = [f"## {self.icon_data} Data & Access Requirements"]
        
        tdp_note = "- Technical Data Package (TDP) available via SAM.gov link."
        cert_note = "- Suppliers must have a current **DD2345 (JCP Certification)** for militarily critical technical data."
        itar_note = "- Suppliers must follow ITAR/export‑controlled document handling procedures."
        
        output.append(tdp_note)
        output.append(cert_note)
        output.append(itar_note)
        
        # Add any specific certifications
        if compliance.get('required_certifications'):
            output.append(f"\n**Required Certifications:**")
            for cert in compliance['required_certifications']:
                output.append(f"- {cert}")
        
        return "\n".join(output)
    
    def _generate_submission_section(self, analysis: Dict) -> str:
        """Generate Submission Details section"""
        
        submission = analysis.get('submission', {})
        
        method = submission.get('method', 'Email')
        email = submission.get('email', 'contracting.officer@agency.mil')
        due_date = submission.get('due_date', 'TBD')
        notice_id = analysis.get('notice_id', analysis.get('contract_id', 'CONTRACT-ID'))
        
        eval_basis = submission.get('evaluation_basis', 'Lowest price, technically acceptable (LPTA)')
        
        output = [f"## {self.icon_submission} Submission Details"]
        
        output.append(f"""
- **Quote Submission:**
  {method} proposal (PDF preferred) to {email}
  Subject line: **Proposal Submission {notice_id} (Company Name)**

- **Due Date:** {due_date}

- **Evaluation Basis:**
  - {eval_basis}
  - "All or None" clause applies --- partial bids not accepted (if applicable)""")
        
        # POC if available
        overview = analysis.get('overview', {})
        if overview.get('poc_name'):
            output.append(f"""
- **Contracting Officer:**
  {overview.get('poc_name', 'Name')}
  Phone: {overview.get('poc_phone', 'N/A')}
  Email: {overview.get('poc_email', email)}""")
        
        return "\n".join(output)
    
    def _generate_delivery_summary_table(self, analysis: Dict) -> str:
        """Generate compact delivery summary table"""
        
        clins = analysis.get('clins', [])
        delivery = analysis.get('delivery_requirements', {})
        
        if not clins:
            return ""
        
        ship_to_short = "Agency Location"
        ship_to = delivery.get('ship_to_address', {})
        if isinstance(ship_to, dict):
            ship_to_short = f"{ship_to.get('organization', '')} {ship_to.get('city', '')}, {ship_to.get('state', '')}"
        
        output = [f"## {self.icon_delivery} Delivery Summary Table\n"]
        
        output.append("| CLIN | Item | Quantity | Start Date | Frequency | Inspection | Ship To | Contract Year |")
        output.append("|------|------|----------|------------|-----------|------------|---------|---------------|")
        
        lead_time = delivery.get('lead_time_days', 'TBD')
        freq = delivery.get('delivery_frequency', 'As Ordered')
        insp = delivery.get('inspection_point', 'Origin')
        
        for idx, clin in enumerate(clins):
            clin_num = clin.get('clin', f"{idx+1:04d}")
            desc = clin.get('description', 'Item')
            qty = clin.get('quantity', 0)
            unit = clin.get('unit', 'EA')
            
            start = f"{lead_time} Days ARO" if idx == 0 else "As Ordered"
            year = f"Year {idx+1}"
            
            output.append(f"| {clin_num} | {desc} | {qty} {unit} | {start} | {freq} | {insp} | {ship_to_short} | {year} |")
        
        return "\n".join(output)
    
    def _generate_requirements_summary(self, analysis: Dict) -> str:
        """Generate plain-language summary"""
        
        specs = analysis.get('specifications', {})
        quality = analysis.get('quality_requirements', {})
        delivery = analysis.get('delivery_requirements', {})
        compliance = analysis.get('compliance', {})
        
        drawing = specs.get('drawing_number', specs.get('manufacturer_part_number', 'N/A'))
        qual_std = quality.get('quality_standard', 'ISO 9001:2015')
        ship_to = delivery.get('ship_to_address', {})
        ship_location = "TBD"
        if isinstance(ship_to, dict):
            ship_location = f"{ship_to.get('organization', 'Agency')} ({ship_to.get('city', '')}, {ship_to.get('state', '')})"
        
        lead_time = delivery.get('lead_time_days', 'TBD')
        freq = delivery.get('delivery_frequency', 'as ordered')
        
        # Contract duration
        clins = analysis.get('clins', [])
        duration = f"{len(clins)}-year" if len(clins) > 1 else "single-year"
        
        total_min = 0
        total_max = 0
        for clin in clins:
            qty = int(clin.get('quantity', 0)) if str(clin.get('quantity', 0)).isdigit() else 0
            total_max += qty
            if 'minimum' in str(clin.get('notes', '')).lower():
                total_min = qty
        
        if total_min == 0:
            total_min = total_max
        
        output = [f"## {self.icon_summary} Summary of What They Require\n"]
        output.append("**In Plain Terms:**\n")
        
        requirements = [
            f"Supply **{analysis.get('title', 'Product')} per Drawing {drawing}** built to military specifications.",
            f"Meet **{qual_std}** or equivalent quality standard.",
            f"**Inspect and accept at origin,** coordinate with inspection agency before shipment.",
            f"Deliver to **{ship_location}** FOB {delivery.get('fob_point', 'Destination')}.",
            f"**Lead time:** Initial delivery starting {lead_time} days ARO; {freq}.",
            f"**{duration.capitalize()} indefinite contract** (Min {total_min} EA / Max {total_max} EA total over life of contract).",
            "Participate in electronic submission processes (WAWF invoicing, SAM registration).",
            "Follow special **packaging, preservation, and labeling** per MIL‑STD‑2073‑1 & MIL‑STD‑129.",
            "Maintain **traceability documentation** for 10 years after final payment.",
            "Possess approved **JCP certification** to access restricted Technical Data Packages (TDPs)."
        ]
        
        for req in requirements:
            output.append(f"- {req}")
        
        return "\n".join(output)
    
    def _generate_vendor_tip(self) -> str:
        """Generate Quick Vendor Tip section"""
        return f"""## {self.icon_tip} Quick Vendor Tip

1. Create a submission calendar using the deadlines above.
2. Verify your SAM registration is active for the relevant NAICS code.
3. Ensure all technical submittals are in PDF format.
4. Copy the Camp Sable Point of Contact on all correspondence."""

    def _generate_closing(self) -> str:
        """Generate document closing"""
        return """---

**End of Vendor RFQ**

*For questions or clarifications, contact john@campsable.com*"""


class EnhancedProductProcessor:
    """
    Enhanced processor that integrates with existing workflow
    Focuses on PRODUCT solicitations only
    """
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.output_generator = VendorListOutputGenerator()
        
        # Pattern library for product detection
        self.PRODUCT_INDICATORS = [
            r'\bNSN\b',
            r'\bCAGE\b.*\bCode\b',
            r'\bPart\s+Number\b',
            r'\bP/N\b',
            r'\bDrawing\s+No',
            r'\bMIL-STD-\d+',
            r'\bspecification\s+\d+',
            r'\bEach\b.*\bEA\b',
            r'\bsupply\b',
            r'\bequipment\b',
            r'\bmaterial\b',
            r'\bhardware\b',
            r'\bcomponent\b',
            r'\bassembly\b'
        ]
        
        self.SERVICE_INDICATORS = [
            r'\bPWS\b',
            r'\bSOW\b',
            r'\bStatement\s+of\s+Work\b',
            r'\bPerformance\s+Work\s+Statement\b',
            r'\bmaintenance\b',
            r'\brepair\b',
            r'\bservice\b.*\bhours\b',
            r'\blabor\s+categories\b',
            r'\bsite\s+visit\b',
            r'\bacres?\b',
            r'\bplanting\b',
            r'\blandscape\b'
        ]
    
    def is_product_solicitation(self, text: str) -> bool:
        """
        Determine if solicitation is for products vs services
        
        Args:
            text: Full solicitation text
            
        Returns:
            True if product, False if service
        """
        product_score = 0
        service_score = 0
        
        text_lower = text.lower()
        
        for pattern in self.PRODUCT_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                product_score += 1
        
        for pattern in self.SERVICE_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                service_score += 1
        
        # Special override: If "repair" appears with NSN, still classify as product
        if re.search(r'\brepair\b', text_lower) and re.search(r'\bNSN\b', text, re.IGNORECASE):
            # Check if it's repair OF a product (product-based) vs repair SERVICE
            if re.search(r'\bCAGE\b', text, re.IGNORECASE) or re.search(r'\bP/N\b', text, re.IGNORECASE):
                product_score += 2
        
        return product_score > service_score
    
    def process_and_generate_vendor_rfq(self, contract_id: str) -> Optional[str]:
        """
        Main entry point: Process a contract and generate vendor RFQ
        
        Args:
            contract_id: Contract ID from database
            
        Returns:
            Formatted RFQ string or None if not a product solicitation
        """
        
        print(f"\n{'='*80}")
        print(f"Processing Contract: {contract_id}")
        print(f"{'='*80}\n")
        
        # 1. Load analysis from database
        if self.db_manager:
            analysis_row = self.db_manager.get_analysis_by_contract_id(contract_id)
            if not analysis_row:
                print(f"❌ No analysis found for {contract_id}")
                return None
            
            analysis = json.loads(analysis_row['analysis_json'])
        else:
            # Load from file if no DB
            analysis_path = f"data/solicitations/{contract_id}/analysis.json"
            if not os.path.exists(analysis_path):
                print(f"❌ No analysis file found: {analysis_path}")
                return None
            
            with open(analysis_path, 'r') as f:
                analysis = json.load(f)
        
        # 2. Check if it's a product solicitation
        description = analysis.get('description', '')
        title = analysis.get('title', '')
        specs = analysis.get('specifications', {})
        
        # Construct full text from all available info to ensure detection
        specs_text = json.dumps(specs) # Includes keys like 'nsn', 'cage'
        full_text = f"{title} {description} {specs_text}"
        
        if not self.is_product_solicitation(full_text):
            print("⚠️  This appears to be a SERVICE solicitation, not PRODUCT")
            print("   Skipping Vendor List generation (use Services template instead)")
            return None
        
        print("✅ Confirmed: PRODUCT solicitation")
        
        # 3. Generate vendor RFQ
        print("\n📝 Generating Vendor RFQ in Claude Vendor List format...")
        
        rfq_output = self.output_generator.generate_vendor_rfq(analysis)
        
        # 4. Save output
        output_dir = f"data/solicitations/{contract_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "vendor_rfq.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rfq_output)
        
        print(f"✅ Vendor RFQ saved: {output_path}")
        
        # 5. Also save as timestamped version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(output_dir, f"vendor_rfq_{timestamp}.md")
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(rfq_output)
        
        print(f"📦 Backup saved: {backup_path}")
        
        return rfq_output

class DeepCrawlEnhancer:
    """
    Enhances SamGovAgent with additional deep crawling capabilities
    Specifically targets external portals and attachment discovery
    """
    
    def __init__(self, sam_agent):
        self.sam_agent = sam_agent
        self.external_domains = [
            'drive.google.com',
            'dropbox.com',
            'box.com',
            'sharepoint.com',
            'army.mil',
            'navy.mil',
            'af.mil',
            'dla.mil',
            'neco.navy.mil',
            'procurement.army.mil'
        ]
    
    def enhanced_link_extraction(self, page_content: str, base_url: str) -> List[str]:
        """
        Enhanced link extraction with priority scoring
        
        Args:
            page_content: HTML content of page
            base_url: Base URL for resolving relative links
            
        Returns:
            Prioritized list of links to crawl
        """
        
        # Extract all URLs
        url_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+'
        found_urls = re.findall(url_pattern, page_content)
        
        # Also check for relative links in common attributes
        rel_patterns = [
            r'href=["\'](\/[^"\']+)["\']',
            r'src=["\'](\/[^"\']+)["\']',
            r'action=["\'](\/[^"\']+)["\']'
        ]
        
        for pattern in rel_patterns:
            rel_matches = re.findall(pattern, page_content)
            for rel in rel_matches:
                try:
                    from urllib.parse import urljoin
                    abs_url = urljoin(base_url, rel)
                    found_urls.append(abs_url)
                except:
                    pass
        
        # Score and prioritize links
        scored_links = []
        for url in set(found_urls):
            url = url.rstrip('.,;:)')
            
            # Skip junk
            junk_patterns = ['.css', '.js', '.jpg', '.png', '.gif', '.ico', 
                           'login', 'register', 'feedback', 'search?', 'mailto:']
            if any(junk in url.lower() for junk in junk_patterns):
                continue
            
            score = 0
            
            # High priority: External portals
            if any(domain in url.lower() for domain in self.external_domains):
                score += 10
            
            # High priority: File extensions
            if any(url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.zip', '.csv']):
                score += 8
            
            # Medium priority: Keywords in URL
            priority_keywords = ['attach', 'doc', 'file', 'download', 'soln', 'rfq', 'specs', 'tdp']
            for kw in priority_keywords:
                if kw in url.lower():
                    score += 3
            
            # Low priority: Same domain navigation
            if 'sam.gov' in url.lower():
                score += 1
            
            if score > 0:
                scored_links.append((score, url))
        
        # Sort by score (highest first)
        scored_links.sort(reverse=True, key=lambda x: x[0])
        
        return [url for score, url in scored_links]
    
    def extract_portal_credentials(self, page_content: str) -> Dict:
        """
        Extract login credentials or access codes mentioned in text
        
        Args:
            page_content: Text content
            
        Returns:
            Dictionary with potential access information
        """
        
        credentials = {
            'usernames': [],
            'access_codes': [],
            'phone_numbers': [],
            'emails': []
        }
        
        # Access codes (e.g., "Access Code: ABC123")
        code_pattern = r'(?:access|login|entry)\s*(?:code|key|id)[:\s]+([A-Z0-9-]+)'
        codes = re.findall(code_pattern, page_content, re.IGNORECASE)
        credentials['access_codes'].extend(codes)
        
        # Phone numbers for help desk
        phone_pattern = r'(\d{3}[-.]?\d{3}[-.]?\d{4})'
        phones = re.findall(phone_pattern, page_content)
        credentials['phone_numbers'].extend(phones)
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_content)
        credentials['emails'].extend(emails)
        
        return credentials
    
    def save_portal_access_info(self, contract_id: str, portal_url: str, credentials: Dict):
        """
        Save portal access information for manual review if needed
        
        Args:
            contract_id: Contract identifier
            portal_url: URL of the portal
            credentials: Extracted credential information
        """
        
        output_dir = f"data/solicitations/{contract_id}/portal_info"
        os.makedirs(output_dir, exist_ok=True)
        
        info_file = os.path.join(output_dir, "portal_access_info.txt")
        
        with open(info_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Portal URL: {portal_url}\n")
            f.write(f"Discovery Time: {datetime.now().isoformat()}\n")
            f.write(f"{'='*80}\n\n")
            
            if credentials['access_codes']:
                f.write("Access Codes Found:\n")
                for code in credentials['access_codes']:
                    f.write(f"  - {code}\n")
                f.write("\n")
            
            if credentials['emails']:
                f.write("Contact Emails:\n")
                for email in credentials['emails']:
                    f.write(f"  - {email}\n")
                f.write("\n")
            
            if credentials['phone_numbers']:
                f.write("Contact Phone Numbers:\n")
                for phone in credentials['phone_numbers']:
                    f.write(f"  - {phone}\n")
                f.write("\n")
            
            f.write("NOTE: If portal requires authentication, contact the above to request access.\n")
            f.write("Some portals may require CAC card or specific registration.\n\n")
        
        print(f"    [Portal Info] Saved access information: {info_file}")


class AttachmentQualityChecker:
    """
    Validates downloaded attachments to ensure completeness
    """
    
    def __init__(self):
        self.min_file_sizes = {
            '.pdf': 1024,      # 1 KB minimum
            '.docx': 512,
            '.xlsx': 512,
            '.doc': 512,
            '.txt': 100
        }
    
    def validate_attachments(self, contract_dir: str) -> Dict:
        """
        Check attachment quality and identify issues
        
        Args:
            contract_dir: Directory containing attachments
            
        Returns:
            Validation report dictionary
        """
        
        report = {
            'total_files': 0,
            'valid_files': 0,
            'suspicious_files': [],
            'missing_key_documents': [],
            'recommendations': []
        }
        
        attachment_dir = os.path.join(contract_dir, "attachments")
        if not os.path.exists(attachment_dir):
            report['recommendations'].append("No attachments directory found")
            return report
        
        key_document_types = ['sf 1449', 'solicitation', 'amendment', 'pricing', 'tdp', 'specification']
        found_key_docs = []
        
        for root, dirs, files in os.walk(attachment_dir):
            for file in files:
                if file.startswith('.'):
                    continue
                
                report['total_files'] += 1
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                file_ext = os.path.splitext(file.lower())[1]
                
                # Check file size
                min_size = self.min_file_sizes.get(file_ext, 0)
                if file_size < min_size:
                    report['suspicious_files'].append({
                        'file': file,
                        'issue': f'File too small ({file_size} bytes)',
                        'path': file_path
                    })
                    continue
                
                # Check for key document types
                file_lower = file.lower()
                for key_doc in key_document_types:
                    if key_doc.replace(' ', '') in file_lower.replace(' ', '').replace('_', ''):
                        found_key_docs.append(key_doc)
                
                report['valid_files'] += 1
        
        # Check for missing key documents
        for key_doc in key_document_types:
            if key_doc not in found_key_docs:
                report['missing_key_documents'].append(key_doc)
        
        # Generate recommendations
        if report['suspicious_files']:
            report['recommendations'].append(
                f"Review {len(report['suspicious_files'])} suspicious files - may be incomplete downloads"
            )
        
        if report['missing_key_documents']:
            report['recommendations'].append(
                f"Missing key documents: {', '.join(report['missing_key_documents'])}"
            )
        
        if report['total_files'] < 3:
            report['recommendations'].append(
                "Very few attachments found - may need manual download or deeper crawl"
            )
        
        return report
    
    def generate_quality_report(self, contract_id: str, validation: Dict):
        """
        Generate a quality report file
        
        Args:
            contract_id: Contract identifier
            validation: Validation results dictionary
        """
        
        output_dir = f"data/solicitations/{contract_id}"
        report_path = os.path.join(output_dir, "attachment_quality_report.txt")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"ATTACHMENT QUALITY REPORT\n")
            f.write(f"{'='*80}\n")
            f.write(f"Contract ID: {contract_id}\n")
            f.write(f"Report Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"Total Files: {validation['total_files']}\n")
            f.write(f"Valid Files: {validation['valid_files']}\n")
            f.write(f"Suspicious Files: {len(validation['suspicious_files'])}\n\n")
            
            if validation['suspicious_files']:
                f.write("SUSPICIOUS FILES:\n")
                for item in validation['suspicious_files']:
                    f.write(f"  - {item['file']}: {item['issue']}\n")
                f.write("\n")
            
            if validation['missing_key_documents']:
                f.write("MISSING KEY DOCUMENTS:\n")
                for doc in validation['missing_key_documents']:
                    f.write(f"  - {doc}\n")
                f.write("\n")
            
            if validation['recommendations']:
                f.write("RECOMMENDATIONS:\n")
                for rec in validation['recommendations']:
                    f.write(f"  • {rec}\n")
        
        print(f"    [Quality Check] Report saved: {report_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced SAM.gov Scraper with Product RFQ Generation")
    parser.add_argument("--process-contract", type=str, help="Process specific contract ID (generate RFQ)")
    
    args = parser.parse_args()

    if args.process_contract:
        # Standalone mode to process one contract
        # Mocking DB connection for standalone test or use check_db
        print(f"Processing contract {args.process_contract}...")
        
        # We can try to load from disk
        processor = EnhancedProductProcessor()
        processor.process_and_generate_vendor_rfq(args.process_contract)
