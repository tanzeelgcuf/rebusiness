
import json
import sys
import os

# Ensure we can import the agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'ai_agents/ProposalWriterAgent')))
from proposal_writer import create_bid_request

def test_n00104_formatting():
    # Construct mock data based on the User's provided text
    # This simulates what the extraction agent would produce
    data = {
        "solicitation_type": "SERVICE", # Treat as service to trigger strict formatting
        "notice_id": "N00104-25-Q-NF13",
        "project_title": "Teardown, Evaluate, Repair and/or Modify Cable Assembly, SPEC (NSN: 5995-01-604-0910)",
        "contract_type": "Firm Fixed Price",
        "project_summary": {
            "in_summary": {
                "they_want": "To conduct teardown, evaluation, and repair services on unserviceable CABLE ASSEMBLY,SPEC units (carcasses) to restore them to an operable, 'A' condition stock.",
                "time_frame": "Year 1: requested RTAT of 160 days.",
                "delivery_locations": "Contractor's Facility (TBD at Award)"
            },
            "project_overview": {
                "agency_name": "Department of the Navy (implied by N00104)",
                "set_aside": "Not specified"
            },
            "work_locations": [
                {
                    "site_id": "Contractor Facility",
                    "county": "",
                    "state": "",
                    "acreage": "",
                    "description": "Repair of 2 Units (Base)"
                }
            ],
            "total_work_area": {
                 "base_acres": 0,
                 "option_acres": 0
            }
        },
        "scope_categories": [
            {
                "category": "Repair and Modification Services",
                "description": "Teardown, evaluate, repair and/or modify CABLE ASSEMBLY,SPEC (NSN 5995-01-604-0910) to an operable condition. Includes labor, material, inspection, testing, packaging, and marking."
            }
        ],
        "timeline": {
            "periods": [
                {
                   "year": "Year 1",
                   "date_range": "Upon receipt -> 160 days RTAT",
                   "activities": [
                       "Receipt of unserviceable units",
                       "Teardown & Evaluation (TD&E)",
                       "Submission of FFP quote",
                       "Complete repair",
                       "Final inspection"
                   ]
                }
            ],
            "deliverables": [
                {
                    "name": "Firm-Fixed Price (FFP) Quote for Repair Effort",
                    "due_days": "90 days",
                    "format": "Detailed pricing proposal",
                    "notes": "Submit to Contracting Officer"
                }
            ]
        },
        "compliance": {
            "key_requirements": [
                "Repair meets CAGE 53711, Ref. No. 6964587",
                "Packaging per MIL-STD-2073",
                "Marking per MIL-STD-129/130",
                "Mercury-Free Material",
                "CAV RP Reporting required"
            ],
            "insurance": {
                "general_liability": "Standard Commercial Liability per FAR Part 28",
                "auto_liability": "Standard Commercial Liability per FAR Part 28",
                "workers_comp": "Standard Commercial Liability per FAR Part 28"
            },
            "wage_determination": "Federal Contractor Standards (SCA or Walsh-Healey)"
        },
        "submission": {
             "due_date": "2026-02-23",
             "address": "Contracting Officer (See Solicitation)",
             "required_documents": [
                 "Quote",
                 "Reps and Certs"
             ]
        }
    }
    
    # Generate Output
    output = create_bid_request(data)
    
    # Save
    with open('N00104_verify_output.txt', 'w') as f:
        f.write(output['body'])
        
    print("Generated N00104_verify_output.txt")

if __name__ == "__main__":
    test_n00104_formatting()
