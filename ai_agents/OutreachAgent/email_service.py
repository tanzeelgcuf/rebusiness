import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService:
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.logger = logging.getLogger(__name__)

    def send_email(self, to_email, subject, body, html_body=None):
        """
        Send an email via SMTP.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = to_email

        # Attach text body
        part1 = MIMEText(body, "plain")
        msg.attach(part1)

        # Attach HTML body if provided
        if html_body:
            part2 = MIMEText(html_body, "html")
            msg.attach(part2)

        context = ssl.create_default_context()

        try:
            # Use SMTP_SSL for port 465 or SMTP with STARTTLS for 587
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls(context=context)
            
            with server:
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, to_email, msg.as_string())
            
            self.logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            return False

if __name__ == "__main__":
    # Test Block
    logging.basicConfig(level=logging.INFO)
    
    # Credentials provided by user (WARNING: Hardcoded for test, ideally use env vars)
    # App Password: gwun semw qdwo ckxz
    SERVICE = EmailService(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        sender_email="bobbysmitty078@gmail.com",
        sender_password="gwun semw qdwo ckxz"
    )
    
    # Send test email to self
    SERVICE.send_email("bobbysmitty078@gmail.com", "Test Email from Outreach Agent", "Hello John, this is a test.")
