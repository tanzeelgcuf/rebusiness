
import os
import sys
import csv
import config
import google.genai as genai
from google.genai.types import HttpOptions
import pandas as pd

# Add the parent directory to the Python path to allow imports from other agent directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Configure the generative AI model with the API key from our config file
client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=HttpOptions(api_version="v1"))

def find_naics_codes(keywords):
    """
    Uses a generative AI model to find relevant NAICS codes for a given set of keywords.

    Args:
        keywords (list): A list of keywords to search for.

    Returns:
        list: A list of dictionaries, where each dictionary represents a NAICS code and its description.
    """
    prompt = f"""
    You are a 'NAICS Code Finder Agent'. Your task is to find relevant NAICS codes for the following keywords.
    Return the results as a list of comma-separated values (CSV) with the columns "NAICS Code" and "Description".

    **Keywords:**
    {', '.join(keywords)}

    **Instructions for the AI:**
    -   Find the most relevant NAICS codes related to the provided keywords.
    -   Format the output as a CSV with a header row.
    -   Ensure the NAICS codes are valid and the descriptions are accurate.
    """

    # Send the prompt to the model
    response = client.models.generate_content(model='models/gemini-2.5-flash', contents=prompt)

    # Process the response to extract the CSV data
    lines = response.text.strip().split('\n')
    reader = csv.reader(lines)
    header = next(reader)
    naics_codes = []
    for row in reader:
        if len(row) == 2:
            naics_codes.append({"NAICS Code": row[0], "Description": row[1]})

    return naics_codes

def save_naics_codes_to_csv(naics_codes, filename="naics_codes.csv"):
    """
    Saves a list of NAICS codes to a CSV file.

    Args:
        naics_codes (list): A list of dictionaries, where each dictionary represents a NAICS code.
        filename (str): The name of the CSV file to save to.
    """
    if not naics_codes:
        print("No NAICS codes to save.")
        return

    # Check if file exists to determine if we need to write headers
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['NAICS Code', 'Description']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()
        
        writer.writerows(naics_codes)
    print(f"Saved {len(naics_codes)} NAICS codes to {filename}")

def read_naics_codes_from_xlsx(file_path, column_name=None):
    """
    Reads NAICS codes from an XLSX file using pandas.

    Args:
        file_path (str): The path to the XLSX file.
        column_name (str, optional): The name of the column containing NAICS codes.
                                     If None, assumes the first column contains the codes.

    Returns:
        list: A list of NAICS codes (strings).
    """
    try:
        df = pd.read_excel(file_path)
        if column_name:
            naics_codes = df[column_name].astype(str).tolist()
        else:
            # Assuming Column B is the second column (index 1)
            naics_codes = df.iloc[:, 1].astype(str).tolist()
        print(f"Read {len(naics_codes)} NAICS codes from {file_path}.")
        return naics_codes
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return []
    except Exception as e:
        print(f"An error occurred while reading the XLSX file: {e}")
        return []

if __name__ == "__main__":
    # Example usage
    search_keywords = ["software development", "data processing", "web design"]
    print(f"--- Finding NAICS codes for keywords: {search_keywords} ---")
    
    found_codes = find_naics_codes(search_keywords)
    
    if found_codes:
        print("\n--- Found NAICS Codes ---")
        for code in found_codes:
            print(f"- {code['NAICS Code']}: {code['Description']}")
        
        save_naics_codes_to_csv(found_codes)

    # Example usage for reading from XLSX
    xlsx_file = "../../2022-NAICS-Codes-listed-numerically-2-Digit-through-6-Digit.xlsx"
    print(f"\n--- Reading NAICS codes from XLSX file: {xlsx_file} ---")
    naics_from_xlsx = read_naics_codes_from_xlsx(xlsx_file)
    if naics_from_xlsx:
        print(f"First 5 NAICS codes from XLSX: {naics_from_xlsx[:5]}")
