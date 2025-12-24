
from bs4 import BeautifulSoup
import re
import json

def analyze_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    
    print(f"Title: {soup.title.string if soup.title else 'No title'}")
    
    # 1. Look for standard links
    links = soup.find_all('a')
    print(f"Found {len(links)} links.")
    
    attachment_links = []
    for link in links:
        href = link.get('href')
        text = link.get_text(strip=True)
        if href and ('attachment' in href or '.pdf' in href or 'download' in href):
            attachment_links.append((text, href))
            
    print(f"Potential Attachment Links: {len(attachment_links)}")
    for txt, url in attachment_links:
        print(f" - {txt}: {url}")

    # 2. Look for JSON data usually in SAM.gov (they often put data in script tags)
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            if "downloadUrl" in script.string:
                print("Found 'downloadUrl' in script tag!")
                # Try simple regex extract
                urls = re.findall(r'"downloadUrl":"([^"]+)"', script.string)
                for u in urls:
                    print(f" - JSON URL: {u}")
            if "resourceId" in script.string:
                 print("Found 'resourceId' - potentially useful.")

if __name__ == "__main__":
    analyze_html("sam_page.html")
