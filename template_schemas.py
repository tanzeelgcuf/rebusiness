"""
Template Schemas for SAM.gov Extraction

Defines the exact JSON schemas that match Claude Vendor List.odt (PRODUCT)
and Claude Services List.odt (SERVICE) templates.
"""

# PRODUCT Template Schema (Claude Vendor List.odt)
PRODUCT_SCHEMA = {
    "solicitation_type": "PRODUCT",
    "notice_id": str,
    "title": str,
    "overview": {
        "agency_name": str,
        "agency_address": str,
        "contract_type": str,
        "set_aside": str,
        "solicitation_date": str,
        "quotes_due": str,
        "naics_code": str,
        "naics_description": str,
        "size_standard": str,
        "dpas_rating": str
    },
    "specifications": {
        "item_requested": str,
        "manufacturer_cage": str,
        "manufacturer_part_number": str,
        "nsn": str,
        "description": str
    },
    "clins": [{
        "clin": str,
        "description": str,
        "quantity": str,
        "unit": str,
        "contract_type": str,
        "inspection": str,
        "packaging": str,
        "notes": str
    }],
    "quantity_range": {
        "min": str,
        "max": str
    },
    "packaging": {
        "mil_std": str,
        "preservation": str,
        "qty_per_unit": str,
        "spi": str
    },
    "inspection_testing": {
        "points": str,
        "agency": str,
        "requirements": [str],
        "quality_standard": str
    },
    "delivery_requirements": {
        "fob": str,
        "destination_address": str,
        "schedule": str,
        "acceleration": str,
        "duration_notes": str
    },
    "data_access": [str],
    "submission": {
        "method": str,
        "email": str,
        "subject": str,
        "due_date": str,
        "evaluation": str
    },
    "delivery_summary_table": [{
        "clin": str,
        "item": str,
        "description": str,
        "qty": str,
        "delivery": str,
        "frequency": str,
        "inspection": str,
        "ship_to": str,
        "notes": str
    }],
    "plain_terms_summary": [str],
    "traces_retention": str
}

# SERVICE Template Schema (Claude Services List.odt)
SERVICE_SCHEMA = {
    "solicitation_type": "SERVICE",
    "notice_id": str,
    "project_title": str,
    "project_overview": {
        "title": str,
        "type": str,
        "purpose": str,
        "location": str,
        "total_work_area": str,
        "objective": str,
        "agency": str
    },
    "scope_table": [{
        "category": str,
        "main_tasks": str
    }],
    "timeline_table": [{
        "year": str,
        "dates": str,
        "requirements": str
    }],
    "deliverables_table": [{
        "deliverable": str,
        "due_from_award": str,
        "format": str,
        "submit_to": str,
        "notes": str
    }],
    "work_locations": {
        "summary": str,
        "sites": [{
            "site_id": str,
            "location": str,
            "planting_type": str,
            "acreage": str
        }]
    },
    "compliance_points": [str],
    "acceptance_criteria": [str],
    "bid_instructions": {
        "due_date": str,
        "delivery_options": str,
        "address": str,
        "required_with_bid": [str]
    },
    "in_summary": {
        "they_want": str,
        "time_frame": str,
        "delivery_locations": str
    },
    "contacts": [{
        "role": str,
        "name": str,
        "method": str
    }],
    "attachments": [{
        "id": str,
        "title": str,
        "purpose": str,
        "details": [str]
    }],
    "key_dates_actions": [{
        "action": str,
        "deadline": str,
        "reference": str
    }],
    "summary_for_bidders": [str],
    "vendor_tips": [str],
    "security_compliance": {
        "requirements": [str],
        "training_deadline": str,
        "search_policy": str
    },
    "wage_labor": {
        "type": str,
        "states": [str],
        "notes": str
    },
    "insurance": {
        "general_liability": str,
        "auto_liability": str,
        "workers_comp": str,
        "employers_liability": str
    },
    "clins_breakdown": {
        "base": [{
            "clin": str,
            "description": str,
            "qty": str,
            "unit": str,
            "year": str
        }],
        "options": [{
            "clin": str,
            "description": str,
            "qty": str,
            "unit": str,
            "year": str
        }]
    }
}

def validate_product_schema(data):
    """Validate that extracted data matches PRODUCT schema"""
    required_fields = [
        "notice_id",
        "title",
        "overview",
        "specifications",
        "clins",
        "delivery_requirements",
        "submission"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, f"Missing required fields: {missing}"
    
    return True, "Valid"

def validate_service_schema(data):
    """Validate that extracted data matches SERVICE schema"""
    required_fields = [
        "notice_id",
        "project_title",
        "project_overview",
        "scope_table",
        "timeline_table",
        "deliverables_table"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, f"Missing required fields: {missing}"
    
    return True, "Valid"

def classify_solicitation_type(data):
    """
    Classify solicitation as PRODUCT or SERVICE based on indicators
    """
    text = str(data).lower()
    
    product_score = 0
    service_score = 0
    
    # Product indicators
    if any(word in text for word in ["nsn", "national stock number", "cage", "cage code", "part number", "p/n"]):
        product_score += 5
    if any(word in text for word in ["supply", "equipment", "material", "hardware", "component", "assembly"]):
        product_score += 2
    if any(word in text for word in ["repair", "overhaul", "modification"]) and any(word in text for word in ["part", "unit", "assembly"]):
        product_score += 4
    
    # Service indicators
    if any(word in text for word in ["pws", "performance work statement", "sow", "statement of work"]):
        service_score += 3
    if any(word in text for word in ["labor", "personnel", "mowing", "landscaping", "janitorial"]):
        service_score += 4
    if any(word in text for word in ["acres", "acreage", "site ", "planting"]):
        service_score += 5
    
    if product_score == 0 and service_score == 0:
        return "PRODUCT"
        
    return "PRODUCT" if product_score >= service_score else "SERVICE"
