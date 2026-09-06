import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Load from config
try:
    import config
    SMTP_CONFIG = config.SMTP_CONFIG
except ImportError:
    SMTP_CONFIG = {
        "smtp_server": os.getenv("SMTP_SERVER"),
        "smtp_port": os.getenv("SMTP_PORT", "587"),
        "smtp_username": os.getenv("SMTP_USERNAME"),
        "smtp_password": os.getenv("SMTP_PASSWORD"),
        "sender_email": os.getenv("SENDER_EMAIL")
    }


@dataclass
class EmailResult:
    """Result of an email send attempt."""
    success: bool
    recipient: str
    subject: str
    error: Optional[str] = None
    message_id: Optional[str] = None


class EmailSender:
    """
    Handles sending RFQ emails to vendors.
    Supports HTML and plain text, with attachments.
    """

    def __init__(self, smtp_config: Optional[Dict[str, str]] = None):
        self.smtp_config = smtp_config or SMTP_CONFIG
        self._validate_config()

    def _validate_config(self):
        """Validate SMTP configuration."""
        required = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'sender_email']
        missing = [key for key in required if not self.smtp_config.get(key)]
        if missing:
            logger.warning(f"SMTP config missing: {missing}. Emails will fail.")

    def send_rfq_email(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachment_path: Optional[str] = None,
        attachment_filename: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> EmailResult:
        """
        Send an RFQ email to a vendor.

        Args:
            recipient_email: Vendor email address
            subject: Email subject line
            body_text: Plain text body
            body_html: Optional HTML body
            attachment_path: Path to RFQ document (PDF/DOCX)
            attachment_filename: Filename for attachment (defaults to basename)
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            EmailResult with success status
        """
        if not self.smtp_config.get('smtp_server'):
            return EmailResult(
                success=False,
                recipient=recipient_email,
                subject=subject,
                error="SMTP not configured"
            )

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_config['sender_email']
            msg['To'] = recipient_email
            msg['Subject'] = subject

            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)

            # Attach plain text
            msg.attach(MIMEText(body_text, 'plain'))

            # Attach HTML if provided
            if body_html:
                msg.attach(MIMEText(body_html, 'html'))

            # Attach file if provided
            if attachment_path and os.path.exists(attachment_path):
                filename = attachment_filename or os.path.basename(attachment_path)
                with open(attachment_path, 'rb') as f:
                    attachment = MIMEApplication(f.read(), Name=filename)
                attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(attachment)
                logger.info(f"Attached {filename} to email")

            # Send
            server = smtplib.SMTP(self.smtp_config['smtp_server'], int(self.smtp_config['smtp_port']))
            server.starttls()
            server.login(self.smtp_config['smtp_username'], self.smtp_config['smtp_password'])

            recipients = [recipient_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)

            server.sendmail(self.smtp_config['sender_email'], recipients, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {recipient_email}")
            return EmailResult(success=True, recipient=recipient_email, subject=subject)

        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return EmailResult(success=False, recipient=recipient_email, subject=subject, error=str(e))

    def send_bulk_rfq(
        self,
        contacts: List[Dict[str, Any]],
        rfq_content: str,
        rfq_type: str,
        attachment_path: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> List[EmailResult]:
        """
        Send RFQ emails to multiple vendors.

        Args:
            contacts: List of vendor contacts with 'email', 'name', 'website'
            rfq_content: Full RFQ markdown/text content
            rfq_type: "PRODUCT" or "SERVICE"
            attachment_path: Path to RFQ document
            custom_message: Optional custom message to prepend

        Returns:
            List of EmailResult objects
        """
        results = []

        for contact in contacts:
            email = contact.get('email')
            name = contact.get('name', 'Vendor')

            if not email:
                logger.warning(f"No email for {name}, skipping")
                results.append(EmailResult(
                    success=False, recipient='unknown', subject='',
                    error="No email address"
                ))
                continue

            # Generate subject
            subject = f"Request for Quote - {rfq_type} - {name}"

            # Generate body
            body_text = self._generate_email_body(rfq_content, name, rfq_type, custom_message)
            body_html = self._generate_email_html(rfq_content, name, rfq_type, custom_message)

            result = self.send_rfq_email(
                recipient_email=email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                attachment_path=attachment_path
            )
            results.append(result)

            # Small delay between sends
            import time
            time.sleep(1)

        return results

    def _generate_email_body(self, rfq_content: str, vendor_name: str, rfq_type: str, custom_message: Optional[str]) -> str:
        """Generate plain text email body."""
        lines = []

        if custom_message:
            lines.append(custom_message)
            lines.append("")

        lines.append(f"Dear {vendor_name},")
        lines.append("")
        lines.append(f"Camp Sable, LLC is requesting a quote for the following {rfq_type.lower()} requirement.")
        lines.append("")
        lines.append("Please find the complete Request for Quote details below:")
        lines.append("")
        lines.append("-" * 60)
        lines.append(rfq_content)
        lines.append("-" * 60)
        lines.append("")
        lines.append("We would appreciate your prompt response with pricing and lead time.")
        lines.append("Please reply to this email or contact us at bobbysmitty078@gmail.com")
        lines.append("with any questions.")
        lines.append("")
        lines.append("Thank you,")
        lines.append("Bobby Smitty")
        lines.append("CampSable LLC")
        lines.append("bobbysmitty078@gmail.com")
        lines.append("+1 (720) 980-6080")

        return "\n".join(lines)

    def _generate_email_html(self, rfq_content: str, vendor_name: str, rfq_type: str, custom_message: Optional[str]) -> str:
        """Generate HTML email body."""
        # Convert markdown to simple HTML
        html_content = rfq_content.replace('\n', '<br>')
        html_content = html_content.replace('### ', '<h3>').replace('## ', '<h2>').replace('# ', '<h1>')
        html_content = html_content.replace('**', '<strong>').replace('__', '<strong>')
        html_content = html_content.replace('*', '<em>').replace('_', '<em>')

        custom_html = f"<p>{custom_message}</p>" if custom_message else ""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .rfq-content {{ background: #f9f9f9; padding: 20px; border-radius: 5px; white-space: pre-wrap; }}
        .header {{ border-bottom: 2px solid #0066cc; padding-bottom: 10px; margin-bottom: 20px; }}
        .footer {{ border-top: 1px solid #ddd; padding-top: 20px; margin-top: 20px; font-size: 0.9em; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Request for Quote - {rfq_type}</h2>
        </div>
        <p>Dear {vendor_name},</p>
        {custom_html}
        <p>Camp Sable, LLC is requesting a quote for the following {rfq_type.lower()} requirement.</p>
        <p>Please find the complete Request for Quote details below:</p>
        <div class="rfq-content">{html_content}</div>
        <p>We would appreciate your prompt response with pricing and lead time.</p>
        <p>Please reply to this email or contact us at <a href="mailto:bobbysmitty078@gmail.com">bobbysmitty078@gmail.com</a> with any questions.</p>
        <div class="footer">
            <p>Thank you,<br>
            Bobby Smitty<br>
            CampSable LLC<br>
            <a href="mailto:bobbysmitty078@gmail.com">bobbysmitty078@gmail.com</a><br>
            +1 (720) 980-6080</p>
        </div>
    </div>
</body>
</html>
"""
        return html


def send_rfq_email(
    recipient_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachment_path: Optional[str] = None
) -> EmailResult:
    """Convenience function for single email send."""
    sender = EmailSender()
    return sender.send_rfq_email(
        recipient_email=recipient_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        attachment_path=attachment_path
    )


if __name__ == "__main__":
    # Test with a mock
    sender = EmailSender()
    result = sender.send_rfq_email(
        recipient_email="test@example.com",
        subject="Test RFQ",
        body_text="Test body"
    )
    print(f"Result: {result}")