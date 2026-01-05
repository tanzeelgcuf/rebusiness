import json
import os
from run_email_campaign import format_service_email_body, format_product_email_body

def generate_samples():
    # --- SERVICE SAMPLE ---
    sol_id_s = "W912ES26BA007"
    sol_title_s = "Fargo–Moorhead Forest Planting"
    product_name_s = "Tree Planting"
    quantity_s = "500 Acres"
    specs_s = "Standard Reforestation"
    
    analysis_data_s = {
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
    
    subject_s, body_s, html_s = format_service_email_body(sol_id_s, sol_title_s, product_name_s, quantity_s, specs_s, "{}", None, None, "2025-01-28", "http://example.com", json.dumps(analysis_data_s))
    
    with open("sample_service_email.txt", "w") as f:
        f.write(f"SUBJECT: {subject_s}\n")
        f.write("-" * 40 + "\n")
        f.write(body_s)
    
    # --- PRODUCT SAMPLE ---
    sol_id_p = "SPRDL1-25-Q-0166"
    sol_title_p = "Cable Assembly Spec"
    product_name_p = "Cable Assembly"
    quantity_p = "118 EA"
    specs_p = "Mil-Spec Cable"
    
    analysis_data_p = {
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
    
    subject_p, body_p, html_p = format_product_email_body(sol_id_p, sol_title_p, product_name_p, quantity_p, specs_p, "{}", None, None, "2026-01-22", "http://example.com", json.dumps(analysis_data_p))
    
    with open("sample_product_email.txt", "w") as f:
        f.write(f"SUBJECT: {subject_p}\n")
        f.write("-" * 40 + "\n")
        f.write(body_p)

    print("Sample emails saved to 'sample_service_email.txt' and 'sample_product_email.txt'")

if __name__ == "__main__":
    generate_samples()
