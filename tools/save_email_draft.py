import base64
from email.mime.text import MIMEText
from google_calendar import get_gmail_service

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "save_email_draft",
        "description": "Saves an email as a draft in the user's Gmail. Should be used if the user asks to cancel or save a draft for later.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "The email address of the recipient.",
                },
                "subject": {
                    "type": "string",
                    "description": "The subject of the email.",
                },
                "body": {
                    "type": "string",
                    "description": "The content/body of the email.",
                }
            },
            "required": ["to", "subject", "body"],
        },
    },
}

def run(to: str, subject: str, body: str) -> str:
    """
    Saves a draft email in the user's Gmail account.
    """
    service = get_gmail_service()
    if not service:
        return "Could not connect to Gmail API."

    try:
        signature = "\n\n--\nSheldon"
        # Add signature if it's not already there to prevent duplicates
        if not body.rstrip().endswith("--\nSheldon"):
            body += signature

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"message": {"raw": raw_message}}
        
        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        return f"Draft saved successfully. Draft ID: {draft['id']}"

    except Exception as e:
        return f"An error occurred while saving the draft: {e}" 