import sys
import os
import logging
import time
import json
import google.generativeai as genai

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import GEMINI_API_KEY
from ai_agents.ResponseAgent.email_monitor import EmailMonitor
from ai_agents.OutreachAgent.email_service import EmailService
from database_manager import DatabaseManager

class ResponseAgent:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Init DB
        self.db = DatabaseManager()
        
        # Init Gemini
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        else:
            self.logger.warning("No GEMINI_API_KEY found.")
            self.model = None

        # Init Email Components
        # HARDCODED CREDENTIALS (Synced with OutreachAgent)
        self.email_user = "john@campsable.com"
        self.email_pass = "gwun semw qdwo ckxz"
        
        self.monitor = EmailMonitor("imap.gmail.com", self.email_user, self.email_pass)
        self.sender = EmailService("smtp.gmail.com", 587, self.email_user, self.email_pass)

    def classify_email(self, subject, body):
        """
        Use LLM to classify the email intent.
        """
        if not self.model:
            return {"category": "UNKNOWN", "reason": "No LLM"}

        prompt = f"""
        You are an AI assistant managing an inbox for a procurement manager.
        Classify the following incoming email into one of these categories:
        - QUOTE_RECEIVED: The sender is providing a price quote, attached a bid, or asking for details to provide a quote.
        - QUESTION: The sender is asking a question about the solicitation (specs, quantity, delivery).
        - DECLINE: The sender is declining to bid (e.g., "No quote", "Cannot supply").
        - SPAM: Marketing, newsletters, or irrelevant.
        - AUTO_REPLY: "Out of office", "Message received" automated replies.

        Email Subject: {subject}
        Email Body:
        {body[:2000]}

        Return ONLY a JSON object with keys:
        - "category": [One of the categories above]
        - "summary": [Brief summary of content]
        - "suggested_action": [What should I do?]
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text)
        except Exception as e:
            self.logger.error(f"Classification failed: {e}")
            return {"category": "ERROR", "reason": str(e)}

    def handle_incoming_emails(self):
        """
        Main loop to check and process emails.
        """
        self.logger.info("Checking for new emails...")
        emails = self.monitor.check_for_emails()
        
        if not emails:
            self.logger.info("No new emails.")
            return

        self.logger.info(f"Found {len(emails)} new emails.")
        
        for email_data in emails:
            subject = email_data['subject']
            sender = email_data['from']
            body = email_data['body']
            
            self.logger.info(f"Processing email from {sender}: {subject}")
            
            # 1. Classify
            analysis = self.classify_email(subject, body)
            self.logger.info(f"Classified as: {analysis.get('category')}")
            
            # 2. Act based on Category
            category = analysis.get('category')
            
            if category == 'QUOTE_RECEIVED':
                self.handle_quote(email_data, analysis)
            elif category == 'QUESTION':
                self.handle_question(email_data, analysis)
            elif category == 'DECLINE':
                self.logger.info("Supplier declined. Logging status.")
                # TODO: Update DB status to 'declined'
            else:
                self.logger.info("Skipping (Spam/Auto).")

    def _extract_email_address(self, raw_from):
        """Extracts just the email address from a From header."""
        import re
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', raw_from)
        return match.group(0).lower() if match else None

    def handle_quote(self, email_data, analysis):
        self.logger.info("Handling Quote...")
        
        # 1. Identify Manufacturer
        sender = email_data['from']
        email_addr = self._extract_email_address(sender)
        manufacturer = self.db.get_manufacturer_by_email(f"%{email_addr}%")
        
        if manufacturer:
            self.logger.info(f"Matched quote to manufacturer: {manufacturer['name']}")
            
            # 2. Update Request Status
            req = self.db.get_latest_request_for_manufacturer(manufacturer['id'])
            if req and req['status'] != 'replied':
                import datetime
                self.db.update_manufacturer_request_status(req['id'], 'replied', datetime.datetime.now())
                self.logger.info(f"Updated request {req['id']} status to 'replied'.")
        else:
            self.logger.warning(f"Could not find manufacturer for email: {email_addr}")

        # 3. Send Acknowledgement
        reply = f"Thank you for your quote regarding '{email_data['subject']}'. We have received it and will review it shortly.\n\nBest regards,\nJohn Campbell"
        self.sender.send_email(email_data['from'], f"Re: {email_data['subject']}", reply)
        self.logger.info("Sent acknowledgement.")

    def handle_question(self, email_data, analysis):
        self.logger.info("Handling Question...")
        # For now, just notify admin or send a generic "We are checking"
        # In future, use context to answer.
        pass

if __name__ == "__main__":
    agent = ResponseAgent()
    agent.handle_incoming_emails()
