import sys
import os
import json
import logging
import datetime

# Add ai_agents path
sys.path.append(os.path.abspath('ai_agents'))

from ai_agents.OutreachAgent.email_service import EmailService
from run_email_campaign import format_product_email_body, SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_test_email(recipient_email):
    logger.info(f"--- Sending Test Product Email to {recipient_email} ---")
    
    # Initialize Email Service
    try:
        email_service = EmailService(SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD)
    except Exception as e:
        logger.error(f"Failed to initialize EmailService: {e}")
        return

    # MOCK PRODUCT DATA (Cable Assembly from Verification Plan)
    sol_id = "SPRDL1-25-Q-0166-TEST"
    sol_title = "TEST - Cable Assembly Spec"
    product_name = "Cable Assembly"
    quantity = "118 EA"
    specs = "Mil-Spec Cable Assembly with specific connector types."
    
    analysis_data = {
        "solicitation_category": "Product",
        "soliciting_entity": "DLA Land and Maritime",
        "issuing_agency_address": "Columbus, OH, USA",
        "contract_type": "Firm Fixed Price / Indefinite Quantity",
        "set_aside_type": "Total Small Business Set-Aside",
        "solicitation_date": datetime.date.today().strftime("%Y-%m-%d"),
        "quotes_due_date": (datetime.date.today() + datetime.timedelta(days=14)).strftime("%Y-%m-%d"),
        "contract_id": sol_id,
        "title": sol_title,
        "naics_code": "335931",
        "size_standard": "600 Employees",
        "dpas_rating": "DO-A1",
        "product_details": [{
            "manufacturer_cage": "19200",
            "part_number": "12992465",
            "total_quantity_range": {
                "guaranteed_minimum": "118 EA",
                "maximum_quantity": "373 EA"
            }
        }],
        "packaging_requirements": {
            "level": "Military, Level B",
            "spi_reference": "12992465 Rev A",
            "standard": "MIL-STD-2073-1"
        },
        "inspection_testing": {
            "inspection_point": "Origin",
            "acceptance_point": "Origin",
            "agency": "DCMA",
            "ipi_required": True,
            "requirement_notify_dcma": True
        },
        "clins": [
            {"clin_number": "0011", "quantity": 118, "unit": "EA", "delivery_lead_time": "340 Days ARO", "short_ship_to_location": "DLA Warren"},
            {"clin_number": "0012", "quantity": 64, "unit": "EA", "delivery_lead_time": "As Ordered", "short_ship_to_location": "DLA Warren"},
            {"clin_number": "0013", "quantity": 191, "unit": "EA", "delivery_lead_time": "As Ordered", "short_ship_to_location": "DLA Warren"}
        ],
        "data_access_requirements": {
            "tdp_available": True, 
            "jcp_required": True,
            "itar_controlled": False
        },
        "submission_details": {
            "submit_to_email": "test_buyer@dla.mil",
            "evaluation_basis": "LPTA"
        },
        "delivery_requirements": {
            "fob_point": "Destination",
            "primary_destination_address": "DLA Distribution Depot",
            "acceleration": "Allowed"
        }
    }
    
    analysis_json = json.dumps(analysis_data)
    
    # Format Email
    subject, body, html_body = format_product_email_body(
        sol_id, sol_title, product_name, quantity, specs, 
        "{}", None, None, analysis_data['quotes_due_date'], 
        "http://example.com/solicitation", analysis_json
    )
    
    logger.info("Generated Email Subject: " + subject)
    logger.info("Generated Email Body Length: " + str(len(body)))
    logger.info("Generated HTML Body Length: " + str(len(html_body)))

    # Send
    try:
        success = email_service.send_email(recipient_email, subject, body, html_body=html_body)
        if success:
            logger.info("✅ SUCCESS: Email sent successfully.")
        else:
            logger.error("❌ FAILURE: Email failed to send.")
    except Exception as e:
        logger.error(f"❌ ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_single_test_email.py <recipient_email>")
        sys.exit(1)
    
    recipient = sys.argv[1]
    send_test_email(recipient)
