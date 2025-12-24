import csv
import os
import glob

# Configuration
INPUT_PATTERN = "*.csv"
OUTPUT_FILE = "leads.csv"
FILES_TO_MERGE = ["1.csv", "2.csv", "3.csv", "4.csv", "5.csv"]

# Header Mappings (Short -> Verbose)
HEADER_MAP = {
    "Product": "Product Keyword",
    "Sol ID": "Solicitation ID",
    "Link": "SAM.gov Link",
    "Qty": "Quantity Needed",
    "Specs": "Exact Size/Specs",
    "Material": "Material Composition",
    "Lead Name": "Lead: Company Name",
    "Email": "Lead: Verified Email",
    "Website": "Lead: Website",
    "Location": "Lead: Location",
    "Specialty": "Lead: Specialty"
}

# The target standard header (Verbose)
STANDARD_HEADERS = [
    "Product Keyword", "Solicitation ID", "SAM.gov Link", "Quantity Needed", 
    "Exact Size/Specs", "Material Composition", "Lead: Company Name", 
    "Lead: Verified Email", "Lead: Website", "Lead: Location", 
    "Lead: Specialty", "Extraction Confidence"
]

def get_mapped_row(row, headers):
    """
    Transforms a row dict to match the STANDARD_HEADERS using the map.
    If the file already has verbose headers, they are used directly.
    """
    new_row = {}
    for std_col in STANDARD_HEADERS:
        # 1. Try direct match
        if std_col in row:
            new_row[std_col] = row[std_col]
        else:
            # 2. Try reverse mapping (find which short header maps to this std_col)
            # This is inefficient 0(N) but fine for small header sets
            found = False
            for short_h, verbose_h in HEADER_MAP.items():
                if verbose_h == std_col and short_h in row:
                    new_row[std_col] = row[short_h]
                    found = True
                    break
            if not found:
                 new_row[std_col] = "" # Default empty
    return new_row

def main():
    print(f"Starting merge of {FILES_TO_MERGE}...")
    
    total_leads = 0
    
    # Check if files exist
    valid_files = [f for f in FILES_TO_MERGE if os.path.exists(f)]
    if not valid_files:
        print("No input files found!")
        return

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=STANDARD_HEADERS)
        writer.writeheader()
        
        for filename in valid_files:
            print(f"Processing {filename}...", end="")
            try:
                with open(filename, 'r', encoding='utf-8', errors='replace') as in_f:
                    # Detect format by sniffing or just reading headers
                    reader = csv.DictReader(in_f)
                    file_headers = reader.fieldnames
                    
                    if not file_headers:
                        print(" Empty file.")
                        continue

                    # Process rows
                    count = 0
                    for row in reader:
                        normalized_row = get_mapped_row(row, file_headers)
                        writer.writerow(normalized_row)
                        count += 1
                        total_leads += 1
                    
                    print(f" Added {count} leads.")

            except Exception as e:
                print(f" Error reading {filename}: {e}")

    print(f"\nSuccessfully merged {len(valid_files)} files into {OUTPUT_FILE}.")
    print(f"Total leads: {total_leads}")

if __name__ == "__main__":
    main()
