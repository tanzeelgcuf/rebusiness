import json
import sqlite3
import os

def extract_urls():
    urls = set()

    # 1. Process JSON files
    json_files = [
        'solicitation_details.json',
        'solicitation_details_products.json'
    ]

    for file_name in json_files:
        if os.path.exists(file_name):
            try:
                with open(file_name, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            # Extract main URL
                            if 'url' in item and item['url']:
                                urls.add(item['url'].strip())
                            
                            # Extract attachment URLs
                            if 'attachments' in item and isinstance(item['attachments'], list):
                                for attachment in item['attachments']:
                                    if 'url' in attachment and attachment['url']:
                                        urls.add(attachment['url'].strip())
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
        else:
            print(f"File not found: {file_name}")

    # 2. Process Database
    db_file = 'rebusiness_automation.db'
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check for solicitations table
            try:
                cursor.execute("SELECT url FROM solicitations WHERE url IS NOT NULL")
                rows = cursor.fetchall()
                for row in rows:
                    if row[0]:
                        urls.add(row[0].strip())
            except sqlite3.Error as e:
                print(f"Error querying solicitations table: {e}")

            # Check for attachments table
            try:
                cursor.execute("SELECT url FROM attachments WHERE url IS NOT NULL")
                rows = cursor.fetchall()
                for row in rows:
                    if row[0]:
                        urls.add(row[0].strip())
            except sqlite3.Error as e:
                print(f"Error querying attachments table: {e}")

            conn.close()
        except Exception as e:
            print(f"Error processing database {db_file}: {e}")
    else:
        print(f"Database file not found: {db_file}")

    # Output unique URLs
    print(f"Found {len(urls)} unique URLs:")
    for url in sorted(urls):
        print(url)

if __name__ == "__main__":
    extract_urls()
