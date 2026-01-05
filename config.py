import os

# Gemini API Key
GEMINI_API_KEY = "AIzaSyBj_3MTLIsmog13YCZ1EVIe4TCfYnFcHQY"

# Google Maps API Key - Paste your Google Maps API key here
GOOGLE_MAPS_API_KEY = "AIzaSyAYaSGXxq0TxntpEOINapwXuZ67F4Nayck"

# SAM.gov Login Credentials - fetched from environment variables
SAM_GOV_CONFIG = {
    "username": os.getenv("SAM_GOV_USERNAME"),
    "password": os.getenv("SAM_GOV_PASSWORD")
}

# SMTP Configuration for sending emails - fetched from environment variables
# Note: For Cloud Run, direct SMTP might be tricky. Consider using a dedicated email service API if issues arise.
SMTP_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER"),
    "smtp_port": os.getenv("SMTP_PORT", "587"), # Default to 587 if not set, ensure it's a string
    "smtp_username": os.getenv("SMTP_USERNAME"),
    "smtp_password": os.getenv("SMTP_PASSWORD"),
    "sender_email": os.getenv("SENDER_EMAIL")
}

# Twilio Configuration for sending SMS and handling calls - fetched from environment variables
TWILIO_CONFIG = {
    "account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
    "auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER")
}

# OpenAI API Key - Paste your OpenAI API key here
OPENAI_API_KEY = "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"

# LLM Provider ("gemini" or "openai") - Defaulting to gemini as requested
LLM_PROVIDER = "gemini"

# Search Keywords - can remain as a list or be fetched from env if dynamic
SEARCH_KEYWORDS = ["products", "supplies", "materials", "equipment", "procurement"]

# Company Information for Proposal Writing
# These are less sensitive, but could also be managed via env vars if needed.
COMPANY_INFO = {
    "NAME": "CampSable LLC",
    "MISSION_STATEMENT": """Our mission is to foster meaningful progress through integrity, innovation, and collaboration. We strive to create a positive and lasting impact for our clients, partners, and the communities we serve by upholding the highest standards of professionalism and respect. We believe in the power of connection — bridging diverse perspectives, backgrounds, and experiences to cultivate understanding and mutual growth. By broadening our cultural horizons and embracing inclusion, we aim to strengthen the relationships that drive success and inspire new ideas. Through responsible practices, continuous learning, and an unwavering commitment to ethical conduct, we seek to contribute to a more resilient, informed, and compassionate world. Our work is guided by respect for people, appreciation for diversity, and dedication to building trust with every action we take. We do not measure our success by output alone, but by the integrity of our process, the strength of our partnerships, and the positive influence we leave behind.""",
    "ABOUT_US": """Camp Sable LLC is a Colorado-based logistics and procurement\ncompany dedicated to supporting the operational needs of\nfederal, commercial, and institutional clients. Formerly focused\non construction, we have redefined our mission to align with\nthe evolving priorities of today's supply chains—delivering\nintegrated procurement strategies, agile logistics coordination,\nand end-to-end sourcing solutions.\nOur experienced team leverages years of government\ncontracting knowledge to help agencies improve acquisition\nefficiency, ensure timely delivery, and maintain compliance\nwith all federal regulations. We work closely with clients to\nmanage complex procurement workflows, reduce costs, and\ndrive supply chain performance.""",
    "CORE_COMPETENCIES": """● Procurement Services: Strategic sourcing, vendor\nmanagement, government acquisition support, and\ncontract fulfillment.\n● Logistics Management: Freight coordination,\nwarehousing, inventory control, and last-mile delivery for\nfederal agencies.\n● Supply Chain Solutions: Integrated planning, risk\nmanagement, and lifecycle supply chain services.\n● Consulting & Compliance: FAR-compliant procurement\nstrategy, logistics workflow optimization, and readiness\nassessments.""",
    "WHY_CHOOSE_US": """Experienced Team: Skilled professionals with extensive\nexperience in federal logistics, procurement planning, and\ncontract compliance.\nCompliance-Driven: We understand the strict requirements of\nfederal acquisitions and align our services with all applicable\nregulations (FAR, DFARS, etc.).\nMission-Focused Execution: From sourcing to delivery, we\nexecute with efficiency and precision—on time, within budget,\nand aligned with mission needs.""",
    "COMPANY_SNAPSHOT": {
        "Legal Business Name": "CampSable LLC",
        "Point of Contact": "John Campbell",
        "UEI": "R7ERBNQAGKQ8",
        "CAGE Code": "08H05",
        "Socio Economic Status": "Minority Owned",
        "Email": "Johnm2511@yahoo.com",
        "Phone Number": "+1 (720) 980-6080",
        "Physical Address": "14264 Hop Clover Trail"
    },
    "NAICS_CODES": """541614: Process, Physical Distribution, and Logistics\nConsulting Services\n493110: General Warehousing and Storage\n488510: Freight Transportation Arrangement\n423840: Industrial Supplies Merchant Wholesalers\n423430: Computer and Computer Peripheral Equipment and\nSoftware Merchant Wholesalers\n423690: Other Electronic Parts and Equipment Merchant\nWholesalers\n333924: Industrial Truck, Tractor, Trailer, and Stacker\nMachinery Manufacturing"""
}

# SerpAPI Key - fetched from environment variable
SERPAPI_KEY = "7f3f692cf6ad3936add827ab6522cc9c8cf12a37"

# Cloud SQL connection details are handled in database_manager.py using env vars.
# No direct database connection strings needed here.
