import os.path
import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]

class GmailAgent:
    def __init__(self):
        self.creds = self._get_credentials()
        self.service = build("gmail", "v1", credentials=self.creds)

    def _get_credentials(self):
        """
        Handles the OAuth 2.0 flow to get user credentials.
        If a valid token.json exists, it's loaded. Otherwise, a new
        one is created by prompting the user to log in.
        """
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secret.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def create_draft(self, to, subject, body):
        """
        Create and save a draft email.
        """
        try:
            message = EmailMessage()
            message.set_content(body)
            message["To"] = to
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"message": {"raw": encoded_message}}
            
            draft = (
                self.service.users()
                .drafts()
                .create(userId="me", body=create_message)
                .execute()
            )
            print(f"Draft id: {draft['id']}\nDraft message: {draft['message']}")
            return draft
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def send_email(self, to, subject, body):
        """
        Send an email.
        """
        try:
            message = EmailMessage()
            message.set_content(body)
            message["To"] = to
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = {"raw": encoded_message}
            
            sent_message = (
                self.service.users()
                .messages()
                .send(userId="me", body=send_message)
                .execute()
            )
            print(f"Message Id: {sent_message['id']}")
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

if __name__ == '__main__':
    # Example usage:
    gmail_agent = GmailAgent()
    # Note: The first time this is run, it will open a browser window for you to log in.
    
    # Example of creating a draft
    gmail_agent.create_draft(
        to="example@example.com",
        subject="Test Draft from Rebusiness Agent",
        body="This is a test draft created by the Rebusiness Automation system."
    )
    print("Test draft created successfully.")

    # Example of sending an email
    # UNCOMMENT THE FOLLOWING LINES TO TEST SENDING AN EMAIL
    # gmail_agent.send_email(
    #     to="example@example.com",
    #     subject="Test Email from Rebusiness Agent",
    #     body="This is a test email sent by the Rebusiness Automation system."
    # )
    # print("Test email sent successfully.")
