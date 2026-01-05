"""
Template Compliance Verification Script

Tests that the extraction and formatting system produces outputs
that exactly match Claude Vendor List.odt and Claude Services List.odt templates.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from template_schemas import validate_product_schema, validate_service_schema, classify_solicitation_type
from ai_agents.ProposalWriterAgent.proposal_writer import create_bid_request
import json

# Sample PRODUCT extraction (matching Claude Vendor List.odt)
SAMPLE_PRODUCT = {
    "solicitation_type": "PRODUCT",
    "notice_id": "W912ES26BA007",
    "title": "Industrial Bolts - Various Sizes",
    "overview": {
        "agency_name": "U.S. Army Corps of Engineers",
        "agency_address": "441 G Street NW\\nWashington, DC 20314",
        "contract_type": "Firm Fixed Price",
        "set_aside": "Small Business",
        "solicitation_date": "2026-01-01",
        "quotes_due": "2026-01-26 14:00 EST",
        "naics_code": "332722",
        "naics_description": "Bolt, Nut, Screw, Rivet, and Washer Manufacturing",
        "size_standard": "750 employees"
    },
    "specifications": {
        "manufacturer_cage": "12345",
        "manufacturer_part_number": "BOLT-IND-500",
        "nsn": "5306-01-234-5678",
        "description": "Industrial grade steel bolts, Grade 8, zinc plated"
    },
    "clins": [
        {
            "clin": "0001",
            "description": "1st Year -- Industrial Bolts 1/2 inch",
            "quantity": 1000,
            "unit": "EA",
            "type": "FFP",
            "inspection_point": "Origin",
            "acceptance_point": "Destination",
            "quality_level": "Commercial",
            "packaging": "Standard",
            "notes": "Guaranteed Minimum"
        }
    ],
    "delivery_requirements": {
        "fob_point": "Destination",
        "ship_to_address": {
            "organization": "DLA Distribution Center",
            "street": "1234 Supply Road",
            "city": "Richmond",
            "state": "VA",
            "zip": "23297"
        },
        "lead_time_days": 60,
        "delivery_frequency": "Monthly shipments",
        "calculated_first_delivery": "2026-03-27"
    },
    "submission": {
        "method": "Email",
        "email": "contracting.officer@usace.army.mil",
        "due_date": "2026-01-26 14:00 EST",
        "required_forms": ["SF 1449", "Representations and Certifications"],
        "evaluation_basis": "LPTA"
    }
}

# Sample SERVICE extraction (matching Claude Services List.odt)
SAMPLE_SERVICE = {
    "solicitation_type": "SERVICE",
    "notice_id": "W912ES26BA007",
    "project_title": "Fargo-Moorhead Forest Mitigation Planting",
    "project_summary": {
        "contract_type": "3-Year Service Contract",
        "purpose": "Establish, monitor, and maintain native forest habitat as environmental mitigation",
        "total_work_area": {
            "base_acres": 165.4,
            "option_acres": 10.4
        },
        "work_locations": [
            {
                "site_id": "8A",
                "county": "Clay",
                "state": "MN",
                "acreage": 28.8,
                "description": "Floodplain & Savanna"
            },
            {
                "site_id": "32",
                "county": "Cass",
                "state": "ND",
                "acreage": 45.2,
                "description": "River Corridor"
            }
        ]
    },
    "scope_categories": [
        {
            "category": "Forest Establishment",
            "description": "Develop and implement planting, maintenance, and invasive species control plans"
        },
        {
            "category": "Tree & Vegetation Planting",
            "description": "Establish 68.8 acres of new forest and prairie"
        }
    ],
    "timeline": {
        "periods": [
            {
                "year": "Year 1",
                "date_range": "Award → 31 Dec 2026",
                "activities": ["Site prep", "Planting", "Maintenance"]
            },
            {
                "year": "Year 2",
                "date_range": "1 Jan 2027 → 31 Dec 2027",
                "activities": ["Maintenance", "Monitoring", "Invasive control"]
            }
        ],
        "deliverables": [
            {
                "name": "Project Schedule",
                "due_days": 15,
                "format": "Excel or PDF"
            },
            {
                "name": "Monthly Reports",
                "due_days": 30,
                "format": "PDF with maps"
            }
        ]
    },
    "compliance": {
        "key_requirements": ["Safety Plan", "Permits", "Licensed applicators"],
        "insurance": {
            "general_liability": "$1,000,000",
            "auto_liability": "$1,000,000",
            "workers_comp": "As required by state law"
        },
        "wage_determination": "SCA compliance required"
    },
    "submission": {
        "method": "Email",
        "address": "U.S. Army Corps of Engineers\\n441 G Street NW\\nWashington, DC 20314",
        "due_date": "2026-01-26 14:00 EST",
        "required_documents": ["SF 1449", "Capability Statement", "Past Performance"],
        "evaluation_basis": "Best Value"
    }
}

def test_product_template():
    """Test PRODUCT template compliance"""
    print("="*80)
    print("TESTING PRODUCT TEMPLATE (Claude Vendor List.odt)")
    print("="*80)
    
    # Validate schema
    is_valid, message = validate_product_schema(SAMPLE_PRODUCT)
    print(f"\n✓ Schema Validation: {message}")
    
    # Generate RFQ
    rfq = create_bid_request(SAMPLE_PRODUCT, "ABC Industrial Supply")
    
    print(f"\n✓ Subject: {rfq['subject']}")
    print(f"\n✓ Email Body Preview (first 500 chars):")
    print(rfq['body'][:500] + "...")
    
    # Check required sections
    required_sections = [
        "Notice ID:",
        "## Overview",
        "## Items Required",
        "### CLIN Table",
        "## Delivery Requirements",
        "## Submission Details",
        "---end of RFQ---"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in rfq['body']:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"\n✗ Missing sections: {missing_sections}")
    else:
        print(f"\n✓ All required sections present")
    
    # Save to file for manual review
    with open('output_product_rfq.txt', 'w') as f:
        f.write(f"Subject: {rfq['subject']}\\n\\n")
        f.write(rfq['body'])
    print(f"\n✓ Full output saved to: output_product_rfq.txt")
    
    return len(missing_sections) == 0

def test_service_template():
    """Test SERVICE template compliance"""
    print("\\n" + "="*80)
    print("TESTING SERVICE TEMPLATE (Claude Services List.odt)")
    print("="*80)
    
    # Validate schema
    is_valid, message = validate_service_schema(SAMPLE_SERVICE)
    print(f"\n✓ Schema Validation: {message}")
    
    # Generate RFQ
    rfq = create_bid_request(SAMPLE_SERVICE, "Green Forest Services")
    
    print(f"\n✓ Subject: {rfq['subject']}")
    print(f"\n✓ Email Body Preview (first 500 chars):")
    print(rfq['body'][:500] + "...")
    
    # Check required sections
    required_sections = [
        "Notice ID:",
        "## Summary of Project",
        "### Work Locations",
        "## What They Want (Scope of Work)",
        "## Timeline / Period of Performance",
        "## Key Compliance Points",
        "## Submission Details",
        "---end of RFQ---"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in rfq['body']:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"\n✗ Missing sections: {missing_sections}")
    else:
        print(f"\n✓ All required sections present")
    
    # Save to file for manual review
    with open('output_service_rfq.txt', 'w') as f:
        f.write(f"Subject: {rfq['subject']}\\n\\n")
        f.write(rfq['body'])
    print(f"\n✓ Full output saved to: output_service_rfq.txt")
    
    return len(missing_sections) == 0

def test_classification():
    """Test solicitation type classification"""
    print("\\n" + "="*80)
    print("TESTING SOLICITATION TYPE CLASSIFICATION")
    print("="*80)
    
    product_type = classify_solicitation_type(SAMPLE_PRODUCT)
    service_type = classify_solicitation_type(SAMPLE_SERVICE)
    
    print(f"\n✓ Product classification: {product_type} (expected: PRODUCT)")
    print(f"✓ Service classification: {service_type} (expected: SERVICE)")
    
    return product_type == "PRODUCT" and service_type == "SERVICE"

if __name__ == "__main__":
    print("\\n" + "="*80)
    print("TEMPLATE COMPLIANCE VERIFICATION")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("Product Template", test_product_template()))
    results.append(("Service Template", test_service_template()))
    results.append(("Classification", test_classification()))
    
    # Summary
    print("\\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\\n✓ ALL TESTS PASSED - Templates are compliant!")
    else:
        print("\\n✗ SOME TESTS FAILED - Review output files")
    
    print("\\nNext steps:")
    print("1. Review output_product_rfq.txt and compare with Claude Vendor List.odt")
    print("2. Review output_service_rfq.txt and compare with Claude Services List.odt")
    print("3. Test with real SAM.gov data using main_workflow.py")
