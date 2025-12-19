
from bs4 import BeautifulSoup

def parse_thomasnet_html(file_path):
    with open(file_path, 'r') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    suppliers = []
    
    # 1. Parse "Suppliers by Name" list
    # Selector: .search-list__list > li
    supplier_list = soup.select('.search-list__list li')
    
    print(f"Found {len(supplier_list)} items in list")
    
    for item in supplier_list:
        link = item.find('a')
        if link:
            name = link.get_text().strip()
            href = link.get('href')
            
            # Text often looks like "Company Name – City, State" - extracting text node after link is tricky in bs4 simple calls
            # converting to string to parse location
            full_text = item.get_text() # "A-Best Industrial – San Pedro, CA"
            location = full_text.replace(name, '').strip(' –-')
            
            suppliers.append({
                'name': name,
                'profile_url': f"https://www.thomasnet.com{href}" if href.startswith('/') else href,
                'location': location,
                'source': 'ThomasNet HTML'
            })
            
    return suppliers

if __name__ == "__main__":
    results = parse_thomasnet_html('thomasnet_sample.html')
    for s in results:
        print(s)
