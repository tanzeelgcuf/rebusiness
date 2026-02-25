import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add path to reach the module
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'ai_agents/ResponseAgent')))

# Import the class to test (assuming the file is named email_monitor.py)
try:
    from email_monitor import EmailMonitor
except ImportError:
    # Try alternate path if running from root
    sys.path.append(os.path.abspath('ai_agents/ResponseAgent'))
    from email_monitor import EmailMonitor

class TestEmailMonitor(unittest.TestCase):
    
    def setUp(self):
        self.server = "imap.test.com"
        self.user = "test@test.com"
        self.password = "password"
        self.monitor = EmailMonitor(self.server, self.user, self.password)

    @patch('imaplib.IMAP4_SSL')
    def test_connect_success(self, mock_imap):
        # Setup mock
        instance = mock_imap.return_value
        instance.login.return_value = ('OK', [b'Logged in'])
        
        # Test
        result = self.monitor.connect()
        
        # Verify
        self.assertTrue(result)
        self.assertIsNotNone(self.monitor.mail)
        instance.login.assert_called_with(self.user, self.password)

    @patch('imaplib.IMAP4_SSL')
    def test_connect_failure(self, mock_imap):
        # Setup mock to raise exception
        mock_imap.side_effect = Exception("Connection failed")
        
        # Test
        result = self.monitor.connect()
        
        # Verify
        self.assertFalse(result)
        self.assertIsNone(self.monitor.mail)

    def test_parse_simple_email(self):
        # Mock the mail object
        self.monitor.mail = MagicMock()
        self.monitor.mail.search.return_value = ('OK', [b'1'])
        
        # Create a simple email
        msg = MIMEText('Hello World')
        msg['Subject'] = 'Test Subject'
        msg['From'] = 'sender@example.com'
        
        # Convert to bytes for header and body
        raw_email = msg.as_bytes()
        
        # Mock fetch response
        # Structure of fetch response in imaplib is [(header, body), closing] depending on implementation
        # The code expects: list of tuples where tuple[1] is the raw bytes
        self.monitor.mail.fetch.return_value = ('OK', [(b'1 (RFC822 {100}', raw_email), b')'])
        
        # Test
        emails = self.monitor.check_for_emails()
        
        # Verify
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]['subject'], 'Test Subject')
        self.assertEqual(emails[0]['from'], 'sender@example.com')
        self.assertIn('Hello World', emails[0]['body'])

    def test_parse_multipart_email(self):
        # Mock the mail object
        self.monitor.mail = MagicMock()
        self.monitor.mail.search.return_value = ('OK', [b'1'])
        
        # Create multipart email
        msg = MIMEMultipart()
        msg['Subject'] = 'Multipart Test'
        msg['From'] = 'sender@example.com'
        msg.attach(MIMEText('Multipart Body', 'plain'))
        msg.attach(MIMEText('<html><body>HTML Body</body></html>', 'html'))
        
        raw_email = msg.as_bytes()
        
        self.monitor.mail.fetch.return_value = ('OK', [(b'1 (RFC822 {500}', raw_email), b')'])
        
        # Test
        emails = self.monitor.check_for_emails()
        
        # Verify
        self.assertEqual(len(emails), 1)
        self.assertIn('Multipart Body', emails[0]['body'])
        # The code in check_for_emails favors text/plain, so it should extract that

if __name__ == '__main__':
    unittest.main()
