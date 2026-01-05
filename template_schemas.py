"""
Template Schemas for SAM.gov Extraction

Defines the exact JSON schemas that match Claude Vendor List.odt (PRODUCT)
and Claude Services List.odt (SERVICE) templates.
"""

# PRODUCT Template Schema (Claude Vendor List.odt)
PRODUCT_SCHEMA = {
    "solicitation_type": "PRODUCT",
    "notice_id": str,  # Required - EXACT match from SAM.gov
    "title": str,
    "overview": {
        "agency_name": str,
        "agency_address": str,  # Complete multi-line address
        "contract_type": str,  # FFP, T&M, Cost-Plus, etc.
        "set_aside": str,  # Small Business, WOSB, HUBZone, 8(a), Unrestricted
        "solicitation_date": str,  # YYYY-MM-DD
        "quotes_due": str,  # YYYY-MM-DD HH:MM TZ
        "naics_code": str,  # 6-digit code
        "naics_description": str,
        "size_standard": str  # "### employees" or "$##.# million"
    },
    "specifications": {
        "manufacturer_cage": str,  # 5-character code
        "manufacturer_part_number": str,
        "nsn": str,  # Format: ####-##-###-####
        "description": str  # Complete technical description
    },
    "clins": [{
        "clin": str,
        "description": str,
        "quantity": int,
        "unit": str,  # EA, LB, etc.
        "type": str,  # FFP, etc.
        "inspection_point": str,  # Origin, Destination
        "acceptance_point": str,
        "quality_level": str,  # Military Level A/B/C
        "packaging": str,  # MIL-STD-2073-1, etc.
        "notes": str  # Guaranteed Minimum, Optional, etc.
    }],
    "delivery_requirements": {
        "fob_point": str,  # Origin or Destination
        "ship_to_address": {
            "organization": str,
            "street": str,
            "city": str,
            "state": str,
            "zip": str
        },
        "lead_time_days": int,  # Days ARO
        "delivery_frequency": str,  # "24 units every 30 days"
        "calculated_first_delivery": str,  # YYYY-MM-DD
        "acceleration_allowed": bool
    },
    "inspection_testing": {
        "inspection_point": str,
        "acceptance_point": str,
        "inspection_agency": str,  # DCMA, DCQA, etc.
        "quality_standard": str  # ISO 9001:2015, etc.
    },
    "packaging_requirements": {
        "mil_std": str,  # MIL-STD-2073-1
        "preservation_level": str,  # Military Level A/B/C
        "labeling_standard": str  # MIL-STD-129
    },
    "submission": {
        "method": str,  # Email, Hand-carry, Mail, Portal
        "email": str,
        "address": str,  # If mail submission
        "due_date": str,  # YYYY-MM-DD HH:MM TZ
        "required_forms": [str],  # ["SF 1449", "Bid Bond"]
        "evaluation_basis": str  # LPTA, Best Value
    },
    "points_of_contact": {
        "contracting_officer": {
            "name": str,
            "agency": str,
            "email": str,
            "phone": str
        }
    }
}

# SERVICE Template Schema (Claude Services List.odt)
SERVICE_SCHEMA = {
    "solicitation_type": "SERVICE",
    "notice_id": str,  # Required - EXACT match from SAM.gov
    "project_title": str,
    "project_summary": {
        "contract_type": str,  # "3-Year Service Contract"
        "purpose": str,  # High-level objective
        "total_work_area": {
            "base_acres": float,
            "base_units": str,  # acres, square feet, etc.
            "option_acres": float,
            "option_units": str
        },
        "work_locations": [{
            "site_id": str,
            "county": str,
            "state": str,
            "acreage": float,
            "description": str,  # "Floodplain & Savanna"
            "contract_type": str  # "Base" or "Option"
        }]
    },
    "scope_categories": [{
        "category": str,  # "Forest Establishment"
        "description": str  # Detailed task description
    }],
    "timeline": {
        "periods": [{
            "year": str,  # "Year 1"
            "date_range": str,  # "Award → 31 Dec 2026"
            "activities": [str]  # ["Site prep", "Planting"]
        }],
        "deliverables": [{
            "name": str,  # "Project Schedule"
            "due_days": int,  # Business days from award
            "format": str,  # "Excel or PDF"
            "submission_to": str  # "Contracting Officer"
        }]
    },
    "performance_standards": {
        "end_of_contract_requirements": [str],
        "acceptance_process": str,
        "deficiency_handling": str
    },
    "compliance": {
        "key_requirements": [str],  # ["Safety Plan", "Permits"]
        "insurance": {
            "general_liability": str,  # "$1,000,000"
            "auto_liability": str,
            "workers_comp": str
        },
        "wage_determination": str,  # "SCA compliance required"
        "safety_standards": [str],  # ["EM 385-1-1", "OSHA"]
        "environmental_permits": [str]  # ["NPDES", "NDPDES"]
    },
    "approved_materials": [{
        "material_type": str,  # "Herbicide"
        "product_name": str,
        "form": str,
        "use_type": str,
        "notes": str
    }],
    "submission": {
        "method": str,  # Email, Hand-carry, Mail
        "email": str,
        "address": str,  # Complete mailing address
        "due_date": str,  # YYYY-MM-DD HH:MM TZ
        "required_documents": [str],  # ["SF 1449", "Capability Statement"]
        "evaluation_basis": str,  # LPTA, Best Value
        "special_clauses": [str]  # ["All or None"]
    },
    "points_of_contact": {
        "contracting_officer": {
            "name": str,
            "agency": str,
            "email": str,
            "phone": str
        },
        "qa_poc": {
            "name": str,
            "phone": str,
            "email": str
        }
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
    
    # Validate nested requirements
    if not data.get("clins"):
        return False, "CLINs list is empty"
    
    if not data.get("delivery_requirements", {}).get("ship_to_address"):
        return False, "Ship-to address is missing"
    
    return True, "Valid"

def validate_service_schema(data):
    """Validate that extracted data matches SERVICE schema"""
    required_fields = [
        "notice_id",
        "project_title",
        "project_summary",
        "scope_categories",
        "timeline",
        "compliance",
        "submission"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, f"Missing required fields: {missing}"
    
    # Validate nested requirements
    if not data.get("scope_categories"):
        return False, "Scope categories list is empty"
    
    if not data.get("project_summary", {}).get("work_locations"):
        return False, "Work locations are missing"
    
    return True, "Valid"

def classify_solicitation_type(data):
    """
    Classify solicitation as PRODUCT or SERVICE based on indicators
    
    PRODUCT indicators: NSN, CAGE, Part Number, physical items
    SERVICE indicators: PWS, SOW, labor categories, site locations
    """
    text = str(data).lower()
    
    product_score = 0
    service_score = 0
    
    # Product indicators
    if any(word in text for word in ["nsn", "national stock number", "cage", "cage code", "part number", "p/n"]):
        product_score += 5  # High weight for hardware IDs
    if any(word in text for word in ["supply", "equipment", "material", "hardware", "component", "assembly"]):
        product_score += 2
    if any(word in text for word in ["repair", "overhaul", "modification"]) and any(word in text for word in ["part", "unit", "assembly"]):
        product_score += 4  # Item-based services are better as PRODUCT format
    
    # Service indicators
    if any(word in text for word in ["pws", "performance work statement", "sow", "statement of work"]):
        service_score += 3
    if any(word in text for word in ["labor", "personnel", "mowing", "landscaping", "janitorial"]):
        service_score += 4
    if any(word in text for word in ["acres", "acreage", "site ", "planting"]):
        service_score += 5  # High weight for environmental services
    
    # Tie-breaker or default
    if product_score == 0 and service_score == 0:
        return "PRODUCT" # Default to product as it's more common for our use case
        
    return "PRODUCT" if product_score >= service_score else "SERVICE"
