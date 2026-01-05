import json
import datetime
from run_email_campaign import format_service_email_body, format_product_email_body

def test_service_template():
    print("\n\n=== TEST 1: Service Template (Claude Services List) ===")
    
    sol_id = "SOL-SERVICE-001"
    sol_title = "Forest Planting Services"
    product_name = "Tree Planting"
    quantity = "500 Acres"
    specs = "Standard Reforestation"
    
    analysis_data = {
        "solicitation_category": "Service",
        "soliciting_entity": "U.S. Army Corps of Engineers (USACE) – St. Paul District",
        "contract_type": "Firm Fixed Price Contract",
        "set_aside_type": "100% for Women-Owned Small Business (WOSB)",
        "title": "Fargo–Moorhead Forest Planting",
        "contract_id": "W912ES26BA007",
        "quotes_due_date": "January 28, 2025, 2:00 PM Central Time",
        "project_scope": {
            "task_descriptions": [
                {"task": "Tree planting services for reforestation/mitigation"},
                {"task": "One base line item and one optional line item"},
                {"task": "Invasive species removal (Forest Preservation Areas)"},
                {"task": "Annual Monitoring Reports"}
            ],
            "work_site_list": [
                {"site_name": "Cass County ND"},
                {"site_name": "Clay County MN"}
            ]
        },
        "compliance": {
            "security_clearance_needed": "All personnel must complete required DoD/Army security training within 30 days of starting."
        },
        "wage_rates": "Service Contract Act (SCA) wage determinations for MN and ND apply.",
        "insurance_limits": "$1,000,000 General Liability, $500,000 Auto Liability.",
        "submission_checklist": [
            "Completed SF 1449 (Blocks 17 & 30)",
            "Bid bond (SF 24) – 20% of bid price",
            "Itemized Pricing Sheet",
            "Completed Representations & Certifications"
        ],
        "submission_instructions": {
            "method": "Hand-carried or mailed (Address: 332 Minnesota Street, Suite E1500, Saint Paul, MN 55101)"
        },
        "summary": "Qualified forestry or environmental contractor to plant and maintain approximately 175 acres of forest and native prairie over three years.",
        "clins": [
            {"clin": "0001AA", "description": "Initial Contract Submittals", "quantity": "1", "unit": "Each"},
            {"clin": "0001AB", "description": "Site Preparation Activities", "quantity": "68.8", "unit": "Acres"},
            {"clin": "0001AC", "description": "Planting – Bank Stabilization", "quantity": "0.3", "unit": "Acres"}
        ],
        "timeline_deliverables": {
            "reporting_deadlines": [
                {"deliverable": "SPOC Identified", "deadline": "Within 10 business days of award", "reference": "Attachment 1"},
                {"deliverable": "Safety, QC Plans", "deadline": "Within 30 days of award", "reference": "Attachment 1"},
                {"deliverable": "Annual Monitoring Reports", "deadline": "By January 30 of each year", "reference": "Attachment 1"}
            ]
        },
        "delivery_requirements": {
            "schedule_aro": "Mar 1, 2026 – Dec 31, 2028"
        }
    }
    
    analysis_json = json.dumps(analysis_data)
    subject, plain_body, html_body = format_service_email_body(sol_id, sol_title, product_name, quantity, specs, "{}", None, None, "2025-01-28", "http://example.com", analysis_json)
    print(f"Subject: {subject}")
    print("-" * 20)
    print(plain_body)

def test_product_template():
    print("\n\n=== TEST 2: Product Template (Claude Vendor List) ===")
    
    sol_id = "SPRDL1-25-Q-0166"
    sol_title = "Cable Assembly Spec"
    product_name = "Cable Assembly"
    quantity = "118 EA"
    specs = "Mil-Spec Cable"
    
    analysis_data = {
        "solicitation_category": "Product",
        "soliciting_entity": "Defense Logistics Agency (DLA) Weapons Support (Warren)",
        "issuing_agency_address": "6501 E. Eleven Mile Road, Warren, MI 48397-5000",
        "contract_type": "Firm Fixed Price / 5-year IQC",
        "set_aside_type": "100% Small Business Set-Aside",
        "solicitation_date": "December 15, 2025",
        "quotes_due_date": "January 22, 2026",
        "notice_id": "SPRDL1-25-Q-0166",
        "title": "Cable Assembly Spec (NSN: 6150-01-501-1062)",
        "naics_code": "335931 – Cable and Wire Device Manufacturing",
        "size_standard": "600 employees",
        "dpas_rating": "DO-A4 (Defense Priority and Allocation System)",
        "product_details": [{
            "description": "Standard cable assembly for military use per Top Drawing No. 12992465.",
            "manufacturer_cage": "19200",
            "manufacturer_part_number": "12992465",
            "nsn": "6150-01-501-1062",
            "tdp_access": "Technical Data Package (TDP) available via SAM.gov link"
        }],
        "inspection_testing": {
            "inspection_point": "Origin",
            "acceptance_point": "Origin",
            "agency": "DCMA (Defense Contract Management Agency)",
            "ipi_required": True,
            "quality_standard": "ISO 9001:2015 or equivalent"
        },
        "clins": [
            {"clin": "0011", "description": "1st Year – Cable Assembly Spec", "quantity": 118, "unit": "EA", "packaging": "Military, Level B", "notes": "Guaranteed Minimum"},
            {"clin": "0012", "description": "2nd Year – Cable Assembly Spec", "quantity": 64, "unit": "EA", "packaging": "Military, Level B", "notes": "2nd Ordering Year"}
        ],
        "delivery_requirements": {
            "fob_point": "Destination",
            "ship_to_address": "DLA Weapons Support (Warren), 6501 East Eleven Mile Road, Warren, MI 48397-5000",
            "schedule_aro": "340 days ARO",
            "frequency": "24 units every 30 days"
        },
        "compliance": {
            "jcp_certification_required": True
        }
    }
    
    analysis_json = json.dumps(analysis_data)
    subject, plain_body, html_body = format_product_email_body(sol_id, sol_title, product_name, quantity, specs, "{}", None, None, "2026-01-22", "http://example.com", analysis_json)
    print(f"Subject: {subject}")
    print("-" * 20)
    print(plain_body)

if __name__ == "__main__":
    test_service_template()
    test_product_template()
