import os
import sys
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database_manager import DatabaseManager
from config import COMPANY_INFO

# Fix import for workflow execution
# Robust import handling
try:
    from ai_agents.OutreachAgent.form_filler import FormFiller
    from ai_agents.OutreachAgent.email_service import EmailService
except ImportError:
    try:
        from OutreachAgent.form_filler import FormFiller
        from OutreachAgent.email_service import EmailService
    except ImportError:
        from form_filler import FormFiller
        from email_service import EmailService


import asyncio
import json
from datetime import datetime, timedelta

class OutreachAgent:
    def __init__(self, db_manager=None):
        self.db = db_manager if db_manager else DatabaseManager()
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        self.form_filler = FormFiller()
        
        # Sender Config
        self.sender_name = "John Campbell"
        self.sender_email = "john@campsable.com"
        self.sender_company = "CampSable LLC"
        
        # Email Config (Hardcoded for now as provided by user)
        self.email_service = EmailService(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="john@campsable.com",
            sender_password="gwun semw qdwo ckxz"
        )

    def generate_message(self, product_details):
        """
        Generate the subject and body for the outreach message using the strict User Template.
        """
        # Data Extraction
        product_name = product_details.get('product_name', 'Industrial Supplies')
        quantity = product_details.get('quantity', 'As required')
        specs = product_details.get('specifications', 'See Attached Solicitation')
        description = product_details.get('description', f"Supply of {product_name}")
        
        contract_id = product_details.get('contract_id', 'N/A')
        location = product_details.get('location', 'CONUS')
        
        # Date Logic
        current_date_str = datetime.now().strftime("%B %d, %Y")
        
        # Response Deadline = Due Date - 4 Days
        due_date_str = product_details.get('due_date')
        response_deadline_str = "[Date]"
        
        if due_date_str and due_date_str != 'N/A':
            try:
                # Assuming YYYY-MM-DD
                dd = datetime.strptime(due_date_str, "%Y-%m-%d")
                deadline = dd - timedelta(days=4)
                response_deadline_str = deadline.strftime("%B %d, %Y")
            except:
                # Fallback: 7 days from now
                deadline = datetime.now() + timedelta(days=7)
                response_deadline_str = deadline.strftime("%B %d, %Y")
        else:
             # Default fallback
             deadline = datetime.now() + timedelta(days=7)
             response_deadline_str = deadline.strftime("%B %d, %Y")

        subject = f"Request for Quote - {contract_id} {product_name}"
        
        # User Provided Template
        message = f"""
Camp Sable, LLC
{self.sender_email}
{current_date_str}

Subject: Request for Quote - {contract_id} {product_name}

Dear Sales Department:

We are writing to request a formal quote for {description}. Camp Sable, LLC is currently evaluating potential suppliers and would appreciate your consideration for this opportunity. Camp Sable, LLC is a registered government procurement company.

Project Details:

Product/Service Required: {product_name}
Quantity Needed: {quantity}
Specifications/Requirements: {specs}

Delivery Timeline: As per solicitation schedule
Delivery Location: {location}

Quote Requirements: Please include the following in your response:
Itemized pricing breakdown
Delivery schedule and shipping costs
Warranty information

Response Deadline: We require your quote to be submitted no later than {response_deadline_str} to ensure timely evaluation of all proposals.

If you have any questions regarding this request or need additional information, please contact me at {self.sender_email}. We look forward to establishing a mutually beneficial business relationship.

Thank you for your time and consideration.

Sincerely,

{self.sender_name}
Procurement Manager
Camp Sable, LLC
"""
        return {"subject": subject, "message": message.strip()}

    def get_pending_outreach(self, limit=10):
        """
        Identify manufacturers that need to be contacted AND the specific product we found them for.
        """
        conn = self.db._connect_db()
        cursor = conn.cursor()
        
        try:
            # JOIN manufacturers -> product_suppliers -> products -> solicitations
            # Fetch Contract ID and Parsed Data (Due Date, Location)
            cursor.execute("""
                SELECT 
                    m.id as manufacturer_id, m.name, m.email, m.website,
                    p.product_name, p.quantity, p.specifications, p.description, p.id as product_id,
                    s.contract_id, s.data
                FROM manufacturers m
                JOIN product_suppliers ps ON m.id = ps.manufacturer_id
                JOIN products p ON ps.product_id = p.id
                JOIN solicitations s ON p.contract_id = s.contract_id
                WHERE (m.email IS NOT NULL OR m.website IS NOT NULL)
                AND m.id NOT IN (SELECT manufacturer_id FROM manufacturer_requests WHERE status = 'sent')
                LIMIT ?
            """, (limit * 5,)) 
            
            rows = cursor.fetchall()
            candidates = []
            
            for row in rows:
                if len(candidates) >= limit: break
                
                # Parse JSON Data from Solicitation
                sol_data = {}
                try:
                    if row[10]: # s.data
                         sol_data = json.loads(row[10])
                except: pass
                
                cand = {
                    'id': row[0],
                    'name': row[1],
                    'email': row[2],
                    'website': row[3],
                    'product_name': row[4],
                    'quantity': row[5],
                    'specifications': row[6],
                    'description': row[7],
                    'product_id': row[8],
                    'contract_id': row[9],
                    'due_date': sol_data.get('due_date'),
                    'location': sol_data.get('location')
                }
                
                # Strict Validation
                if not self._is_valid_url(cand['website']) and not cand['email']:
                    continue
                    
                candidates.append(cand)
                
            return candidates
        finally:
            self.db._close_db()

    def _is_valid_url(self, url):
        """
        Strict URL validation to block generic or irrelevant domains.
        """
        if not url: return False
        
        url_lower = url.lower()
        if len(url) < 10: return False
        
        invalid_keywords = [
            'google.com', 'facebook.com', 'twitter.com', 'linkedin.com',
            'youtube.com', 'instagram.com', 'wikipedia.org', 'amazon.com',
            'reddit.com', 'stackoverflow.com', 'pinterest.com', 
            'chrome/index.html', 'search?', 'login', 'signup'
        ]
        
        if any(keyword in url_lower for keyword in invalid_keywords):
            return False
            
        return True

    def get_detailed_product(self):
        """
        Fetch a random product that HAS specifications and quantity from the database.
        """
        conn = self.db._connect_db()
        cur = conn.cursor()
        try:
            # Prefer products with quantity AND specs
            cur.execute("""
                SELECT p.product_name, p.quantity, p.specifications, p.description, p.contract_id 
                FROM products p
                WHERE p.quantity IS NOT NULL AND p.specifications IS NOT NULL 
                ORDER BY RANDOM() LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return {
                    "product_name": row[0],
                    "quantity": row[1],
                    "specifications": row[2],
                    "description": row[3],
                    "contract_id": row[4]
                }
            
            return {"product_name": "Industrial Supplies"}
        finally:
            self.db._close_db()

    async def send_outreach(self, manufacturer, product_details=None):
        """
        Orchestrate the outreach: Priority Email -> Fallback Form Fill -> Fallback Extracted Email.
        """
        self.logger.info(f"Prepare outreach for: {manufacturer['name']}")
        
        # Priority: 1. Passed details, 2. Details in manufacturer dict (from JOIN), 3. DB Fallback
        if not product_details:
            if 'product_name' in manufacturer and manufacturer['product_name']:
                product_details = {
                    "product_name": manufacturer['product_name'],
                    "quantity": manufacturer.get('quantity'),
                    "specifications": manufacturer.get('specifications'),
                    "description": manufacturer.get('description'),
                    "contract_id": manufacturer.get('contract_id'),
                    "location": manufacturer.get('location'),
                    "due_date": manufacturer.get('due_date')
                }
            else:
                 # Last resort fallback if data is missing (should be rare with new join)
                 product_details = self.get_detailed_product()
        
        content = self.generate_message(product_details)
        
        # Method 1: Form Fill (Primary as per user request)
        form_success = False
        extracted_emails = []
        
        if manufacturer.get('website'):
            self.logger.info(f"Attempting FORM FILL on {manufacturer['website']}")
            
            data = {
                "name": self.sender_name,
                "email": self.sender_email,
                "company": self.sender_company,
                "subject": content['subject'],
                "message": content['message']
            }
            
            try:
                # Call updated form filler (ASYNC)
                result = await self.form_filler.fill_form_async(manufacturer['website'], data)
                extracted_emails = result.get('extracted_emails', [])
                
                if result['success']:
                    self.log_request(manufacturer['id'], status='sent', method='form', payload=str(data))
                    form_success = True
                    self.logger.info("Form fill SUCCESS.")
                else:
                    self.logger.warning(f"Form fill failed: {result.get('error')}")
                    self.log_request(manufacturer['id'], status='failed', method='form', payload=f"Form Error: {result.get('error')}")

            except Exception as e:
                self.logger.error(f"Form fill crashed: {e}")
                self.log_request(manufacturer['id'], status='failed', method='form', payload=str(e))
        
        # Method 2: Email (Secondary/Parallel)
        email_success = False
        target_email = manufacturer.get('email')
        
        # Use extracted email if DB email is missing
        if not target_email and extracted_emails:
            target_email = extracted_emails[0]
            self.update_manufacturer_email(manufacturer['id'], target_email)
            self.logger.info(f"Using extracted email: {target_email}")

        if target_email:
            self.logger.info(f"Attempting EMAIL to {target_email}...")
            # Email service is still synchronous, which is fine as it's fast. 
            # Could be made async later if needed, but blocking time is minimal compared to browser.
            if self.email_service.send_email(
                to_email=target_email,
                subject=content['subject'],
                body=content['message']
            ):
                self.log_request(manufacturer['id'], status='sent', method='email', payload=content['message'])
                email_success = True
                self.logger.info("Email sent SUCCESS.")
            else:
                self.logger.warning("Email send failed.")
        else:
            self.logger.info("No email address available for direct sending.")

        # Return True if AT LEAST one method worked
        return form_success or email_success

    def update_manufacturer_email(self, manufacturer_id, email):
        conn = self.db._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE manufacturers SET email = ? WHERE id = ?", (email, manufacturer_id))
            conn.commit()
            self.logger.info(f"Updated manufacturer {manufacturer_id} email to {email}")
        except Exception as e:
            self.logger.error(f"Failed to update email: {e}")
        finally:
            self.db._close_db()

    def log_request(self, manufacturer_id, status, method, payload):
        conn = self.db._connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO manufacturer_requests (manufacturer_id, status, method, payload, request_date)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (manufacturer_id, status, method, payload))
            conn.commit()
        finally:
            self.db._close_db()

async def main():
    agent = OutreachAgent()
    
    candidate_limit = 500
    pending = agent.get_pending_outreach(limit=candidate_limit)
    print(f"Found {len(pending)} pending outreach targets.")
    
    for manufacturer in pending:
        print(f"Processing: {manufacturer['name']}")
        success = await agent.send_outreach(manufacturer, product_details=None)
        
        if success:
            print(f" -> Outreach SENT ({manufacturer.get('email', 'form')})")
        else:
            print(f" -> Outreach FAILED")
            
    print("Batch processing complete.")

if __name__ == "__main__":
    asyncio.run(main())
