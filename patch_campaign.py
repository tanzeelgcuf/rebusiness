import os

FILE_PATH = "/Users/apple/Downloads/rebusinessautomationproject/run_email_campaign.py"

with open(FILE_PATH, 'r') as f:
    content = f.read()

target = """    contract_type = clean_val(data.get('contract_type'), missing_msg)
    set_aside = clean_val(data.get('set_aside_type'), missing_msg)"""

replacement = """    contract_type = clean_val(data.get('contract_type'), missing_msg)
    set_aside = clean_val(data.get('set_aside_type'), "None")
    if "SOLE SOURCE" in sol_title.upper() or "SOLE SOURCE" in raw_desc.upper():
        set_aside = "Sole Source (Direct Award)"
    elif set_aside == "None" or set_aside == missing_msg:
        set_aside = "Full & Open Competition\""""

if target in content:
    new_content = content.replace(target, replacement)
    with open(FILE_PATH, 'w') as f:
        f.write(new_content)
    print("Successfully patched run_email_campaign.py")
else:
    print("Target string not found!")
