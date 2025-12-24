import json

def test_parsing():
    analysis_json = """{"soliciting_entity": "DEPT OF THE AIR FORCE", "soliciting_contact_info": {"email": "art_louie.lesaca.1@us.af.mil", "phone": "9197221763"}, "product_details": [{"line_item_number": null, "name": "Tremco Alpha Grade sealant", "description": "Tremco Alpha Grade sealant for buildings 3300, 4502, and 2903", "quantity": null, "unit": null, "part_number": null, "specifications": []}], "delivery_location": {"street": "1570 WRIGHT BROTHERS AVE BLDG 2903", "city": "SEYMOUR JOHNSON AFB", "state": "NC", "zip_code": "27531-2456"}, "summary": "This solicitation is for Tremco Alpha Grade sealant...", "contract_id": "d624c7a9ce", "title": "Tremco Alpha Grade", "url": "https://sam.gov/workspace/contract/opp/fd6201b746744132b6183a2fdf6be8f4/view"}"""
    
    print(f"Original Length: {len(analysis_json)}")

    # Logic from run_email_campaign.py (Loop part)
    delivery_loc_json = None
    if analysis_json:
        try:
            data = json.loads(analysis_json)
            target_loc = data.get('delivery_location')
            if target_loc:
                delivery_loc_json = json.dumps(target_loc)
        except Exception as e:
            print(f"Loop Parsing Error: {e}")

    print(f"Extracted Loc JSON: {delivery_loc_json}")

    # Logic from run_email_campaign.py (format_email_body part)
    delivery_loc_str = "As per solicitation requirements"
    try:
        if delivery_loc_json:
            loc_data = json.loads(delivery_loc_json)
            # Extracted format: {street, city, state, zip_code}
            if isinstance(loc_data, dict):
                parts = [loc_data.get(k) for k in ['street', 'city', 'state', 'zip_code'] if loc_data.get(k)]
                if parts:
                    delivery_loc_str = ", ".join(parts)
    except Exception as e:
         print(f"Format Parsing Error: {e}")

    print(f"Final String: {delivery_loc_str}")

if __name__ == "__main__":
    test_parsing()
