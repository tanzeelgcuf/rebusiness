"""
Price Request Agent
Automatically sends wholesale price list requests to manufacturers via Gmail.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pickle
from database_manager import DatabaseManager

SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

class PriceRequestAgent:
    def __init__(self):
        self.db = DatabaseManager()
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API."""
        creds = None
        token_path = 'token.pickle'
        credentials_path = 'credentials.json'
        
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        print("Gmail API authenticated successfully.")
    
    def create_price_request_email(self, manufacturer_name, manufacturer_email, 
                                   product_name, product_specs=None, quantity=None):
        """
        Create a personalized wholesale price request email.
        
        Args:
            manufacturer_name: Name of the manufacturer
            manufacturer_email: Manufacturer's email address
            product_name: Product name
            product_specs: Product specifications (optional)
            quantity: Estimated quantity (optional)
            
        Returns:
            Email message object
        """
        # Email subject
        subject = f"Wholesale Price List Request - {product_name}"
        
        # Email body
        body = f"""Dear {manufacturer_name} Team,

I hope this email finds you well. We are a government contractor currently preparing a bid for a federal solicitation requiring {product_name}.

We are interested in obtaining your wholesale price list for the following:

Product: {product_name}
"""
        
        if product_specs:
            body += f"Specifications: {product_specs}\n"
        
        if quantity:
            body += f"Estimated Quantity: {quantity} units\n"
        
        body += """
Could you please provide us with the following information:

1. Wholesale/bulk pricing structure
2. Lead times for delivery
3. Minimum order quantities (if any)
4. Payment terms
5. GSA Schedule pricing (if applicable)
6. Any volume discounts available

We are committed to building long-term partnerships with reliable manufacturers and look forward to the possibility of working together.

Please feel free to reach out if you need any additional information.

Best regards,
[Your Company Name]
[Your Contact Information]
"""
        
        # Create message
        message = MIMEMultipart()
        message['to'] = manufacturer_email
        message['subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        
        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
    
    def send_price_request(self, manufacturer_id, product_id, manufacturer_email, 
                          manufacturer_name, product_name, product_specs=None, quantity=None):
        """
        Send a price request email to a manufacturer.
        
        Args:
            manufacturer_id: Database ID of manufacturer
            product_id: Database ID of product
            manufacturer_email: Manufacturer's email
            manufacturer_name: Manufacturer's name
            product_name: Product name
            product_specs: Product specifications (optional)
            quantity: Estimated quantity (optional)
            
        Returns:
            Request ID if successful, None otherwise
        """
        print(f"\n--- Sending price request to {manufacturer_name} ---")
        
        try:
            # Create email
            message = self.create_price_request_email(
                manufacturer_name, manufacturer_email, product_name, 
                product_specs, quantity
            )
            
            # Send email
            sent_message = self.service.users().messages().send(
                userId='me', body=message
            ).execute()
            
            email_thread_id = sent_message['threadId']
            print(f"  - Email sent successfully (Thread ID: {email_thread_id})")
            
            # Record request in database
            request_id = self.db.add_manufacturer_request(
                manufacturer_id=manufacturer_id,
                product_id=product_id,
                email_thread_id=email_thread_id,
                notes=f"Initial price request sent for {product_name}"
            )
            
            print(f"  - Request recorded in database (ID: {request_id})")
            return request_id
            
        except Exception as e:
            print(f"  - Error sending price request: {e}")
            return None
    
    def send_follow_up(self, request_id, manufacturer_email, manufacturer_name, product_name):
        """
        Send a follow-up email for a price request.
        
        Args:
            request_id: Database ID of the original request
            manufacturer_email: Manufacturer's email
            manufacturer_name: Manufacturer's name
            product_name: Product name
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n--- Sending follow-up to {manufacturer_name} ---")
        
        subject = f"Follow-up: Wholesale Price List Request - {product_name}"
        
        body = f"""Dear {manufacturer_name} Team,

I wanted to follow up on my previous email regarding wholesale pricing for {product_name}.

We are still very interested in obtaining your price list and would appreciate any information you can provide.

If you need any additional details from our end, please don't hesitate to ask.

Thank you for your time and consideration.

Best regards,
[Your Company Name]
"""
        
        try:
            message = MIMEMultipart()
            message['to'] = manufacturer_email
            message['subject'] = subject
            message.attach(MIMEText(body, 'plain'))
            
            encoded_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
            
            sent_message = self.service.users().messages().send(
                userId='me', body=encoded_message
            ).execute()
            
            print(f"  - Follow-up sent successfully")
            
            # Update request status
            self.db.update_manufacturer_request_status(request_id, 'follow_up_sent')
            
            return True
            
        except Exception as e:
            print(f"  - Error sending follow-up: {e}")
            return False

if __name__ == "__main__":
    # Test the agent
    agent = PriceRequestAgent()
    
    # Test sending a price request
    # Note: Replace with actual manufacturer data from database
    # agent.send_price_request(
    #     manufacturer_id=1,
    #     product_id=1,
    #     manufacturer_email="sales@example.com",
    #     manufacturer_name="Example Manufacturer",
    #     product_name="GeneXpert Analyzer",
    #     product_specs="Model GX-16",
    #     quantity=10
    # )
    
    print("PriceRequestAgent initialized and ready.")
