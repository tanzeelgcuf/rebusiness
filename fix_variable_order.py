import os

FILE_PATH = "/Users/apple/Downloads/rebusinessautomationproject/run_email_campaign.py"

with open(FILE_PATH, 'r') as f:
    lines = f.readlines()

def fix_function(start_keyword, end_keyword):
    global lines
    new_lines = []
    in_func = False
    func_lines = []
    
    for line in lines:
        if start_keyword in line:
            in_func = True
        
        if in_func:
            func_lines.append(line)
            if end_keyword in line and "return" in line:
                # Process the func_lines
                # 1. Find the raw_desc extraction block
                block_start = -1
                block_end = -1
                for i, l in enumerate(func_lines):
                    if "# Fetch raw description for date mining" in l:
                        block_start = i
                    if "except: pass" in l and block_start != -1:
                        block_end = i
                        break
                
                if block_start != -1 and block_end != -1:
                    block = func_lines[block_start:block_end+1]
                    # Remove from original
                    remaining = func_lines[:block_start] + func_lines[block_end+1:]
                    # Insert block after missing_msg definition
                    insert_idx = -1
                    for i, l in enumerate(remaining):
                        if 'missing_msg = "Information not provided in solicitation"' in l:
                            insert_idx = i + 1
                            break
                    
                    if insert_idx != -1:
                        func_lines = remaining[:insert_idx] + ["\n"] + block + remaining[insert_idx:]
                
                new_lines.extend(func_lines)
                in_func = False
                func_lines = []
        else:
            new_lines.append(line)
    
    lines = new_lines

fix_function("def format_service_email_body", "return subject, plain_body, html_body")
fix_function("def format_product_email_body", "return subject, plain_body, html_body")

with open(FILE_PATH, 'w') as f:
    f.writelines(lines)

print("Successfully fixed variable ordering in run_email_campaign.py")
