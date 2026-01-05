import sqlite3
import json

DB_PATH = "rebusiness_automation.db"

ENRICHMENT_MAP = {
    '04f3e1a2905844b994298c793f3ff78e': {
        'naics': '517111',
        'size_std': '1,500 Employees',
        'set_aside': '8(a) Set-Aside (FAR 19.8)',
        'cage': 'N/A (Service)'
    },
    '197aaa46ad6c461db627c6934ba7fea4': {
        'naics': '811210',
        'size_std': '$34.0 Million',
        'set_aside': 'None',
        'cage': 'Information not provided in solicitation'
    },
    '796b8188161049bfa359c2b16432e946': {
        'naics': '236220',
        'size_std': '$45.0 Million',
        'set_aside': 'None',
        'cage': 'N/A (Service)'
    },
    'cc36deeb238c4481888bee066b255901': {
        'naics': '811210',
        'size_std': '$34.0 Million',
        'set_aside': 'None',
        'cage': 'N/A (Service)'
    },
    'a1edf238787e4f4a83a87997bff9087e': {
        'naics': '336413',
        'size_std': '1,250 Employees',
        'set_aside': 'None',
        'cage': '81205 (Boeing)'
    },
    '8e3c806a4472495fb936e1e2493f3304': {
        'naics': '332999',
        'size_std': '750 Employees',
        'set_aside': 'Total Small Business Set-Aside',
        'cage': 'Information not provided in solicitation'
    },
    'd4c90fd103a2402a88d306a6c4dce262': {
        'naics': '541519',
        'size_std': '$34.0 Million',
        'set_aside': 'SDVOSB Set-Aside (FAR 19.14)',
        'cage': 'N/A (Service)'
    },
    'e6fc48127e6041e5943291cf31192b7c': {
        'naics': '339112',
        'size_std': '1,000 Employees',
        'set_aside': 'None',
        'cage': '7KXY2 (Evoqua/Mar Cor)'
    }
}

def deep_enrich():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for cid, data in ENRICHMENT_MAP.items():
        cursor.execute("SELECT analysis_summary FROM solicitations WHERE contract_id = ?", (cid,))
        row = cursor.fetchone()
        if not row: continue
        
        try:
            summary = json.loads(row[0])
            summary['naics_code'] = data['naics']
            summary['size_standard'] = data['size_std']
            summary['set_aside_type'] = data['set_aside']
            
            # Update product details CAGE
            if 'product_details' in summary and summary['product_details']:
                summary['product_details'][0]['manufacturer_cage'] = data['cage']
            
            # Special case for TDP
            summary['data_access_requirements'] = summary.get('data_access_requirements', {})
            summary['data_access_requirements']['tdp_available'] = False # As per browser check
            
            new_json = json.dumps(summary)
            cursor.execute("UPDATE solicitations SET analysis_summary = ? WHERE contract_id = ?", (new_json, cid))
            print(f"Deep Enriched {cid}")
        except Exception as e:
            print(f"Error enriching {cid}: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    deep_enrich()
