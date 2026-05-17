import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS", "credentials/credentials.json")

def get_oauth_flow(redirect_uri):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return flow

def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

def get_gmail_service(credentials_dict):
    creds = Credentials(
        token=credentials_dict["token"],
        refresh_token=credentials_dict["refresh_token"],
        token_uri=credentials_dict["token_uri"],
        client_id=credentials_dict["client_id"],
        client_secret=credentials_dict["client_secret"],
        scopes=credentials_dict["scopes"]
    )
    return build("gmail", "v1", credentials=creds)

def get_new_emails(service, whitelist):
    query = " OR ".join([f"from:{addr}" for addr in whitelist])
    query += " -label:ai-employee-review in:inbox"
    result = service.users().messages().list(
        userId="me",
        q=query
    ).execute()

    messages = result.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}

        body = ""
        payload = msg_data["payload"]
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    break
        elif "body" in payload and "data" in payload["body"]:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

        emails.append({
            "gmail_id": msg["id"],
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "body": body
        })

    return emails

def send_reply(service, to, subject, body):
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = "Re: " + subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

def archive_email(service, gmail_id):
    service.users().messages().modify(
        userId="me",
        id=gmail_id,
        body={
            "removeLabelIds": ["INBOX", "UNREAD"]
        }
    ).execute()

def get_account_email(service):
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]

def get_or_create_label(service, label_name):
    labels = service.users().labels().list(userId="me").execute()
    for label in labels.get("labels", []):
        if label["name"] == label_name:
            return label["id"]
    created = service.users().labels().create(
        userId="me",
        body={"name": label_name}
    ).execute()
    return created["id"]

def label_email(service, gmail_id, label_name):
    label_id = get_or_create_label(service, label_name)
    service.users().messages().modify(
        userId="me",
        id=gmail_id,
        body={"addLabelIds": [label_id]}
    ).execute()