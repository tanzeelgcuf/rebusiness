import imaplib
import email
from email.header import decode_header
import time
import logging
import os

class EmailMonitor:
    def __init__(self, imap_server, email_user, email_pass):
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_pass = email_pass
        self.mail = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_user, self.email_pass)
            self.logger.info("Connected to IMAP successfully.")
            return True
        except Exception as e:
            self.logger.error(f"IMAP connection failed: {e}")
            return False

    def check_for_emails(self, folder="INBOX", peek=False):
        if not self.mail:
            if not self.connect():
                return []

        try:
            self.mail.select(folder)
            # Search for UNSEEN emails
            status, messages = self.mail.search(None, 'UNSEEN')
            
            email_ids = messages[0].split()
            emails = []
            
            # RFC822.PEEK might be causing issues, trying BODY.PEEK[] which is standard for full message
            fetch_cmd = '(BODY.PEEK[])' if peek else '(RFC822)'
            
            for e_id_bytes in email_ids:
                e_id = e_id_bytes.decode()
                self.logger.info(f"Fetching {e_id} with cmd {fetch_cmd}")
                res, msg_data = self.mail.fetch(e_id, fetch_cmd)
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                            
                        from_ = msg.get("From")
                        
                        # Extract body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                
                                if "attachment" not in content_disposition:
                                    if content_type == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                        else:
                            body = msg.get_payload(decode=True).decode()
                            
                        emails.append({
                            "id": e_id,
                            "subject": subject,
                            "from": from_,
                            "body": body,
                            "msg_object": msg # Keep raw object for attachment processing later
                        })
            
            return emails
            
        except Exception as e:
            self.logger.error(f"Error checking emails: {e}")
            return []

    def close(self):
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
