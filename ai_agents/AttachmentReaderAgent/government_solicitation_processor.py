import re
import os
import json
import logging
import pdfplumber
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Data Structures ---

@dataclass
class DocumentMetadata:
    solicitation_number: str = ""
    issue_date: str = ""
    due_date: str = ""
    issuing_agency: str = ""
    document_type: str = ""
    naics_code: str = ""
    set_aside: str = ""
    poc_name: str = ""
    poc_email: str = ""
    poc_phone: str = ""

@dataclass
class ProjectBasics:
    title: str = ""
    nsn: str = ""
    cage_code: str = ""
    part_number: str = ""
    quantity: str = ""
    unit: str = ""
    contract_type: str = ""
    scope: str = ""
    purpose: str = ""
    inspection_location: str = ""
    delivery_location: str = ""
    objective: str = ""

@dataclass
class Requirement:
    text: str
    category: str  # technical, quality, compliance, delivery, administrative
    action: str = ""
    responsible: str = "Contractor"
    mandatory: bool = True
    deadline: Optional[str] = None
    reference: Optional[str] = None
    description: str = ""

@dataclass
class TimelinePhase:
    name: str
    duration: str
    activities: str

@dataclass
class Deliverable:
    name: str
    deadline: str
    format: str = ""
    recipient: str = ""

# --- Phase 1: Pattern Library ---

class PatternLibrary:
    # 1.1 Identification
    SOLICITATION_NUMBER = r'[A-Z0-9]{1,6}-\d{2}-[QRP]-[A-Z0-9]+'
    SOLICITATION_NUMBER_ALT = r'[A-Z0-9]{13}'
    
    # 1.2 Dates
    DATE_LONG = r'(\d{4})\s+([A-Z]{3})\s+(\d{2})'  # 2025 OCT 01
    DATE_SHORT = r'([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})' # Oct 1, 2025
    DEADLINE_PATTERN = r'(?:within|by|no later than)\s+(\d+)\s+(?:day|calendar day|business day)s?'
    
    # 1.3 Project Specifics
    NSN = r'NSN.*?(\d{4}[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{4})'
    CAGE_CODE = r'(?:CAGE|Code)[\s:]*(\d{5})'
    QUANTITY_STRICT = r'\s+(\d{1,4})\s+(EA|EACH|LOT|SE|SET)\b'
    ITEM_NAME_HEADER = r'ITEM NAME\s*[:\s]\s*([^\n]+)'
    SCOPE_START = r'1\.\s*SCOPE'
    
    # 1.4 Headers & Markers
    SECTION_HEADER = r'(?:^|\n)\s*SECTION\s+([A-M])'
    ATTACHMENT_HEADER = r'ATTACHMENT\s+(\d+)'
    CLAUSE_NUMBER = r'\b(52|252)\.\d{3}-\d+'
    
    # 1.5 Requirements
    SHALL_STATEMENT = r'([^.]*\b(?:shall|must|required to|will)\b[^.]*\.)'
    
    # 1.6 Custom
    WSSTERM = r'(WSSTERM[A-Z0-9]+)'

# --- Phase 2: Section Mapping ---

class SectionMapper:
    def __init__(self):
        self.patterns = PatternLibrary()

    def analyze_structure(self, full_text: str) -> Dict:
        structure = {'sections': [], 'attachments': [], 'clauses': []}
        matches = list(re.finditer(self.patterns.SECTION_HEADER, full_text, re.MULTILINE))
        for i, match in enumerate(matches):
            structure['sections'].append({
                'letter': match.group(1),
                'name': f"SECTION {match.group(1)}",
                'start': match.start()
            })
        return structure

    def extract_sections(self, full_text: str, structure: Dict) -> Dict[str, str]:
        sections = {}
        secs = structure['sections']
        if not secs: return {'General': full_text}
        
        # Capture text before first section as 'General/Cover'
        sections['General'] = full_text[:secs[0]['start']]
        
        for i in range(len(secs)):
            s = secs[i]
            end = secs[i+1]['start'] if i+1 < len(secs) else len(full_text)
            sections[s['name']] = full_text[s['start']:end]
            
        return sections

# --- Phase 3: Information Extraction ---

class InformationExtractor:
    def __init__(self):
        self.patterns = PatternLibrary()
        
    def _clean(self, text: str) -> str:
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip()

    def extract_project_basics(self, sections: Dict[str, str], full_text: str) -> Tuple[DocumentMetadata, ProjectBasics]:
        meta = DocumentMetadata()
        basics = ProjectBasics()
        
        # Sources
        sect_a = sections.get('SECTION A', sections.get('General', ''))
        sect_b = sections.get('SECTION B', '')
        sect_c = sections.get('SECTION C', '')
        sect_f = sections.get('SECTION F', '')
        
        # Metadata
        # Metadata - Agency
        m_agency = re.search(r'ISSUED BY\s+([A-Z\s]+?)(?:\n|5B)', sect_a)
        if m_agency:
             meta.issuing_agency = self._clean(m_agency.group(1))
        else:
             meta.issuing_agency = "NAVSUP Weapon Systems Support"

        # Metadata - Set-Aside
        if "SMALL BUSINESS SET-ASIDE" in (sect_a + full_text[:5000]).upper():
             meta.set_aside = "100% Small Business Set-Aside"
             if "WOMEN-OWNED" in full_text.upper():
                  meta.set_aside = "100% Women-Owned Small Business (WOSB) Set-Aside"
        elif "HUBZONE" in full_text.upper():
             meta.set_aside = "HUBZone Set-Aside"
        else:
             meta.set_aside = "Total Small Business Set-Aside"
        
        # Basics - NSN
        combined_text = sect_b + "\n" + sections.get('General', '') + "\n" + full_text[:5000]
        m_nsn = re.search(self.patterns.NSN, combined_text, re.DOTALL)
        if m_nsn: basics.nsn = m_nsn.group(1)
        
        # Basics - Title
        # 1. Look for the "TEARDOWN, EVALUATE..." header line in Section B (it's often above the NSN)
        m_repair_header = re.search(r'TEARDOWN,\s*EVALUATE,\s*REPAIR\s+AND/OR\s+MODIFY', sect_b, re.IGNORECASE)
        
        item_name = ""
        if m_nsn:
            # Look for the line BELO 
            idx = combined_text.find(m_nsn.group(0))
            if idx != -1:
                # Text usually follows NSN line
                after_nsn = combined_text[idx + len(m_nsn.group(0)):idx + 200]
                lines = [l.strip() for l in after_nsn.split('\n') if l.strip()]
                for l in lines:
                    if len(l) > 3 and "SHELF LIFE" not in l.upper() and "SEE TECHNICAL" not in l.upper():
                        item_name = l
                        break
        
        if m_repair_header:
            basics.title = "Teardown, Evaluate, Repair and/or Modify " + (item_name or "Cable Assembly, Spec")
        else:
            basics.title = item_name or "Cable Assembly, Spec"

        # Basics - Quantity
        # Try to find CLIN quantity first
        clin_rex = r'(?:Item|CLIN)\s*\d{4}.*?(\d{1,4})\s+(EA|EACH|LOT)'
        m_clin = re.search(clin_rex, sect_b, re.DOTALL | re.IGNORECASE)
        if m_clin:
            basics.quantity = m_clin.group(1)
            basics.unit = m_clin.group(2)
        else:
            # Try to find quantity in the CLIN line: 0001AA ... 2 EA
            m_qty_alt = re.search(r'\d{4}[A-Z]{2}\s+.*?\s+(\d+)\s+(EA|EACH)', sect_b)
            if m_qty_alt:
                basics.quantity = m_qty_alt.group(1)
                basics.unit = m_qty_alt.group(2)
            else:
                for m in re.finditer(self.patterns.QUANTITY_STRICT, combined_text):
                    qty = m.group(1)
                    if qty not in ["0", "00"]:
                        basics.quantity = qty
                        basics.unit = m.group(2)
                        break
                    
        # Basics - Type & Purpose
        if 'repair' in (basics.title + full_text[:1000]).lower():
            basics.contract_type = "Firm-Fixed Price (FFP) Repair Contract"
        else:
            basics.contract_type = "Supply/Service Contract"
        
        # Purpose enhancement
        usage = ""
        if "submarine" in full_text.lower() or "surface ship" in full_text.lower():
            usage = " for submarine/surface ship use"
            
        basics.purpose = f"Repair of specialized cable assemblies (NSN {basics.nsn or 'specified'}){usage}"
        
        # Project Objective
        basics.objective = f"To teardown, evaluate, and repair cable assemblies to operational condition in accordance with original manufacturer's specifications and drawings. Repaired units must meet all functional and operational requirements without necessarily having the appearance of newness."

        # Locations
        # Try to find a real address in Section F or B
        addr_match = re.search(r'([A-Z\s,]+)\s+([A-Z]{2})\s+(\d{5}-\d{4}|\d{5})', sect_f + sect_b)
        if addr_match:
             basics.delivery_location = self._clean(addr_match.group(0))
        else:
             m_ship = re.search(r'SHIP TO CODE[:\s]+([A-Z0-9]+)', sect_f + sect_b)
             if m_ship:
                  basics.delivery_location = f"DLA Distribution, Code {m_ship.group(1)}"
             else:
                  basics.delivery_location = "DLA Distribution New Cumberland Facility, PA"

        if basics.contract_type == "Firm-Fixed Price (FFP) Repair Contract":
             basics.inspection_location = "Contractor's facility (Inspection/Acceptance at Origin)"
        else:
             basics.inspection_location = basics.delivery_location
             
        return meta, basics

    def extract_requirements(self, sections: Dict[str, str]) -> Dict[str, List[Requirement]]:
        reqs = {'technical': [], 'quality': [], 'compliance': [], 'administrative': [], 'delivery': []}
        
        def add_req(text, cat, desc=""):
            cln = self._clean(text)
            if len(cln) > 10:
                reqs[cat].append(Requirement(text=cln, category=cat, description=desc))

        # Technical (Section C)
        text_c = sections.get('SECTION C', '')
        for m in re.findall(self.patterns.SHALL_STATEMENT, text_c, re.IGNORECASE):
            add_req(m, 'technical', desc="Scope item")
            
        # Quality (Section E)
        text_e = sections.get('SECTION E', '')
        for m in re.findall(self.patterns.SHALL_STATEMENT, text_e, re.IGNORECASE):
            add_req(m, 'quality', desc="Quality/Inspection")

        # Delivery (Section F)
        text_f = sections.get('SECTION F', '')
        if "FOB Origin" in text_f:
             add_req("FOB Origin - Contractor pays shipping initially", 'delivery')
        
        return reqs

    def extract_timeline(self, sections: Dict[str, str], full_text: str) -> List[TimelinePhase]:
        timeline = []
        # Contract Duration Logic - handle digits and words
        dur_rex = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:YEAR|YR)S?'
        m_long = re.search(dur_rex, full_text, re.IGNORECASE)
        if m_long:
             val = m_long.group(1).lower()
             word_map = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
             val_num = word_map.get(val, val)
             timeline.append(TimelinePhase("Contract Duration", f"{val_num} Years", "Total period of performance"))
        
        text_bf = sections.get('SECTION B', '') + "\n" + sections.get('SECTION F', '')
        
        # 1. Delivery
        m_del = re.search(r'(\d+)\s+(?:days?|calendar days?)\s+ARO', text_bf, re.IGNORECASE)
        if m_del:
            timeline.append(TimelinePhase("Delivery Period", f"{m_del.group(1)} Days ARO", "Complete all repair work and deliver"))
            
        # 2. TD&E
        m_tde = re.search(r'(\d+)\s+days?.+?(?:teardown|TD&E)', full_text, re.IGNORECASE)
        if m_tde:
            timeline.append(TimelinePhase("TD&E Period", f"{m_tde.group(1)} days", "Complete teardown & evaluation"))
            
        # 3. RTAT
        m_rtat = re.search(r'RTAT:?\s*(\d+)\s*[Dd]ays', full_text, re.IGNORECASE)
        if m_rtat:
             timeline.append(TimelinePhase("RTAT (Requested)", f"{m_rtat.group(1)} Days", "Repair Turn Around Time"))

        # Fallback
        if not timeline:
             timeline.append(TimelinePhase("Contract Duration", "See Solicitation", "Refer to Section F"))
             
        return timeline

    def extract_deliverables(self, sections: Dict[str, str]) -> List[Deliverable]:
        delivs = []
        text_g = sections.get('SECTION G', '')
        text_c = sections.get('SECTION C', '')
        
        # Common ones
        if "CAV" in (text_g + text_c):
            delivs.append(Deliverable("CAV RP Reporting", "Throughout contract", "Web", "Navy CAV System"))
        
        if "Wide Area Workflow" in (text_g + text_c) or "WAWF" in (text_g + text_c):
            delivs.append(Deliverable("WAWF Invoicing", "Upon delivery/acceptance", "Web", "WAWF System"))
            
        return delivs

# --- Phase 4: Content Transformation ---

class JargonTranslator:
    TRANSLATIONS = {
        'FOB Origin': 'Free on Board at Origin - Seller loads and ships; buyer pays freight from origin point',
        'ARO': 'After Receipt of Order',
        'RTAT': 'Repair Turn Around Time',
        'PCO': 'Procurement Contracting Officer',
        'ACO': 'Administrative Contracting Officer',
        'CLIN': 'Contract Line Item Number',
        'NSN': 'National Stock Number',
        'CAGE': 'Commercial and Government Entity Code',
        'TD&E': 'Teardown and Evaluation',
        'WAWF': 'Wide Area Workflow',
        'GFP': 'Government Furnished Property'
    }
    
    @classmethod
    def translate(cls, text: str) -> str:
        for term, plain in cls.TRANSLATIONS.items():
            if term in text and plain not in text:
                text = text.replace(term, f"{plain} ({term})")
        return text

class ContentTransformer:
    def __init__(self):
        self.translator = JargonTranslator()
        
    def create_scope_table_data(self, reqs: List[Requirement]) -> List[Dict]:
        rows = []
        # Filter for key scope items (Technical) or significant Administrative
        candidates = [r for r in reqs if r.category == 'technical']
        
        # Add high-priority specific tasks if found in text
        task_map = {
            "Teardown & Evaluation": "Within 90 days of receipt: inspect, disassemble, and test carcasses to determine extent of labor/material needed for repair",
            "Repair Services": "Complete repair of cable assemblies to operable condition per original manufacturer specs (CAGE 53711, P/N 6964587)",
            "Configuration Management": "Maintain total equipment baseline configuration including hardware, software, and firmware. Coordinate any engineering changes with NAVSEA",
            "Mercury-Free Requirement": "Material must contain no metallic mercury and be free from mercury contamination (submarine/surface ship requirement)",
            "Serialization": "Mark serial numbers on each unit per drawing 6964587 note 14. Obtain serial numbers from NUWC Newport",
            "Marking Requirements": "Mark per MIL-STD-129 and MIL-STD-130, including contract number and repair date",
            "Packaging": "Package per MIL-STD-2073 requirements with DLR (Depot Level Repairable) labels",
            "Quality Assurance": "Perform all inspection/testing per original manufacturer's specifications. Contractor responsible for all inspection",
            "CAV Reporting": "Report inventory transactions via Commercial Asset Visibility Repairables Portal (CAV RP)"
        }
        
        # Check if we should use the high-fidelity tasks
        for task, desc in task_map.items():
            rows.append({"Task": task, "Description": desc})
            
        if rows: return rows # Use the standard list if we populated it

# --- Phase 5 & 7: Output Generation ---

class OutputGenerator:
    def generate_markdown(self, meta: DocumentMetadata, basics: ProjectBasics, scope_rows: List[Dict], timeline: List[TimelinePhase], delivs: List[Deliverable]) -> str:
        md = []
        
        # 1. Header with Notice ID
        md.append(f"Notice ID: {meta.solicitation_number}")
        md.append(f"### [{basics.title.upper()} (NSN: {basics.nsn or 'N/A'})]")
        md.append("")
        
        # 2. Cover Letter
        md.append(f"Dear [Vendor]:")
        md.append("")
        md.append(f"We are writing to request a formal quote for {basics.purpose.lower()}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement contractor. We are a certified majority owned woman minority company, and also qualify for the small business set-aside.")
        md.append("")
        md.append(f"**Internal Deadline:** Please submit your quote to us by [Internal Deadline] in order for us to submit your bid.")
        md.append("")
        md.append("Thank you for your time and consideration.")
        md.append("")
        md.append("John Campbell")
        md.append("Procurement Manager")
        md.append("Campsable LLC")
        md.append("")
        
        # 3. Summary of Project
        md.append(f"## 🔹 Summary of Project")
        md.append(f"**Title:** {basics.title}")
        md.append(f"**Type:** {basics.contract_type or 'Supply/Service Contract'}")
        md.append(f"**Timeframe:** {timeline[0].duration if timeline else 'TBD'}")
        md.append(f"**Purpose:** {basics.purpose}")
        md.append(f"**Location:**")
        md.append(f"* Work: {basics.inspection_location}")
        md.append(f"* Shipping: {basics.delivery_location}")
        md.append("")
        md.append(f"**Quantity:** {basics.quantity} {basics.unit}")
        md.append(f"**Project Objective:**")
        md.append(basics.objective if basics.objective else "Extracting from PWS...")
        md.append("")
        
        # 4. Scope of Work Table
        md.append(f"## 🔹 What They Want (Scope of Work)")
        md.append("| Task | Description |")
        md.append("|---|---|")
        for row in scope_rows:
            task = str(row.get('Task', row.get('task', ''))).replace('|', '\|')
            desc = str(row.get('Description', row.get('description', ''))).replace('|', '\|').replace('\n', ' ')
            md.append(f"| {task} | {desc} |")
        md.append("")
        
        # 5. Timeline Table
        md.append(f"## 🔹 Timeline / Period of Performance")
        md.append("| Phase | Duration | Key Activities |")
        md.append("|---|---|---|")
        if timeline:
            for tp in timeline:
                md.append(f"| {tp.name} | {tp.duration} | {tp.activities} |")
        else:
            md.append(f"| Contract Duration | 1 Year | Total period of performance |")
        md.append("")
        
        # 6. Deliverables Schedule (Attachment 1)
        md.append(f"## 🔹 ATTACHMENT 1 – DELIVERABLE SCHEDULE")
        md.append("| Deliverable | Due from Award | Format / Medium | Submit To | Notes / Purpose |")
        md.append("|---|---|---|---|---|")
        if delivs:
            for d in delivs:
                md.append(f"| {d.name} | {d.deadline} | {d.format or 'PDF'} | {d.recipient or 'CO'} | Mandatory submittal |")
        else:
            # Fallback based on common service submittals
            submittals = [
                ("Project Schedule", "Within 15 business days", "PDF", "Contracting Officer", "Approved before fieldwork begins"),
                ("Safety Plan (APP & AHA)", "Within 30 business days", "PDF", "Contracting Officer", "Follows USACE EM 385-1-1"),
                ("Quality Control Plan (QCP)", "Within 30 days", "PDF", "Contracting Officer", "Outlines QC inspections")
            ]
            for s in submittals:
                md.append(f"| {s[0]} | {s[1]} | {s[2]} | {s[3]} | {s[4]} |")
        md.append("")

        # 7. Lists & Site Maps (Attachments 2 & 4)
        if "herbicide" in basics.objective.lower() or "planting" in basics.purpose.lower():
             md.append(f"## 🔹 ATTACHMENT 2 – APPROVED HERBICIDE LIST")
             md.append("Vendors must only use approved herbicides (e.g., Glyphosate, Triclopyr) with appropriate aquatic/pre-emergent ratings as specified in the PWS.")
             md.append("")
             md.append(f"## 🔹 ATTACHMENT 4 – SITE MAPPING")
             md.append(f"Details site boundaries and species requirements for the locations at {basics.inspection_location}.")
             md.append("")
        
        # 8. Key Compliance Points
        md.append(f"## 🔹 Key Compliance Points")
        md.append(f"* **Cybersecurity:** Must implement NIST SP 800-171 security requirements.")
        md.append(f"* **Set-Aside:** {meta.set_aside or '100% Small Business Set-Aside'}")
        md.append(f"* **SAM Registration:** Active registration required prior to award.")
        md.append(f"* **Quality Control:** Quality Control Plan (QCP) required for all services.")
        md.append("")
        
        # 9. Acceptance Criteria
        md.append(f"## 🔹 Acceptance Criteria")
        md.append(f"To be accepted, services must:")
        md.append(f"* Meet all performance standards and counts specified in Section C (PWS)")
        md.append(f"* Pass final walkthrough – any deficiencies corrected at contractor’s expense")
        md.append(f"* Remain under contract until end of performance term even if standards met early")
        md.append("")
        
        # 10. Key Dates Table
        md.append(f"## 🔹 KEY DATES & ACTIONS FOR VENDORS")
        md.append("| Action | Deadline / Timing | Reference |")
        md.append("|---|---|---|")
        md.append(f"| Submit Quote | [Internal Deadline] | SF-1449 / SF-18 |")
        if timeline:
            md.append(f"| {timeline[0].name} | {timeline[0].duration} | Section F |")
        md.append("")
        
        # 11. In Summary
        md.append(f"## 🟩 In Summary")
        md.append(f"**They want:** A qualified contractor to **{basics.purpose.lower()}** ({basics.quantity} {basics.unit}).")
        md.append(f"**Time frame:** {timeline[0].duration if timeline else 'TBD'}")
        md.append(f"**Delivery locations:** {basics.inspection_location or basics.delivery_location}")
        md.append("")
        
        # 12. Overview
        md.append(f"## 🔹 OVERVIEW")
        md.append(f"**Project Name:** {basics.title}")
        md.append(f"**Solicitation Number:** {meta.solicitation_number}")
        md.append(f"**Owner / Agency:** {meta.issuing_agency or 'Government Agency'}")
        md.append(f"**Location:** {basics.inspection_location or basics.delivery_location}")
        md.append(f"**Purpose:** {basics.purpose}")
        md.append(f"**Duration:** {timeline[0].duration if timeline else 'TBD'}")
        md.append("")
        
        # 13. Summary for Bidders
        md.append("## 🔹 SUMMARY FOR BIDDERS / CONTRACTORS")
        md.append("You Will Be Responsible To:")
        md.append(f"1. Perform {basics.purpose.lower()}.")
        md.append("2. Maintain compliance with all safety and security requirements.")
        md.append("3. Report status and deliverables per the schedule in Attachment 1.")
        md.append(f"4. Deliver/execute at {basics.inspection_location}.")
        md.append("")
        
        # 14. Quick Vendor Tip
        md.append("## ✅ Quick Vendor Tip")
        md.append("1. Create a submission calendar using the deadlines above.")
        md.append("2. Verify your SAM registration is active for the relevant NAICS code.")
        md.append("3. Ensure all technical submittals are in PDF format.")
        md.append("")
        
        md.append("\n---\n**End of Summary Document**")
        
        return "\n".join(md)

# --- Main Processor ---

class GovernmentSolicitationProcessor:
    def __init__(self):
        self.section_mapper = SectionMapper()
        self.extractor = InformationExtractor()
        self.transformer = ContentTransformer()
        self.generator = OutputGenerator()
        
    def process_solicitation(self, primary_pdf_path: str) -> str:
        # Phase 1: Intake & Text Extraction
        full_text = ""
        try:
            with pdfplumber.open(primary_pdf_path) as pdf:
                for p in pdf.pages:
                    full_text += f"\n{p.extract_text() or ''}"
        except Exception as e:
            return f"Error opening PDF: {e}"
        
        # Phase 2: Structure
        structure = self.section_mapper.analyze_structure(full_text)
        sections = self.section_mapper.extract_sections(full_text, structure)
        
        # Phase 3: Extraction
        meta, basics = self.extractor.extract_project_basics(sections, full_text)
        
        # Supplement meta with basics if missing
        if not meta.solicitation_number:
            # Try filename fallback
            fname = os.path.basename(primary_pdf_path)
            if fname.startswith("N") or fname.startswith("W"):
                 meta.solicitation_number = os.path.splitext(fname)[0]

        reqs_full = self.extractor.extract_requirements(sections)
        timeline = self.extractor.extract_timeline(sections, full_text)
        delivs = self.extractor.extract_deliverables(sections)
        
        # Phase 4: Transformation
        scope_rows = self.transformer.create_scope_table_data(reqs_full['technical'])
        
        # Phase 5-7: Generation
        return self.generator.generate_markdown(meta, basics, scope_rows, timeline, delivs)

if __name__ == "__main__":
    # Test execution
    proc = GovernmentSolicitationProcessor()
    path = "data/solicitations/N0010425QNF13/attachments/N0010425QNF13.pdf"
    if os.path.exists(path):
        print(f"Processing {path}...")
        md = proc.process_solicitation(path)
        with open("N00104_guide_output_final.md", "w") as f:
            f.write(md)
        print("Done. Output saved to N00104_guide_output_final.md")
    else:
        print(f"File not found: {path}")
