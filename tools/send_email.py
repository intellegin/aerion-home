import base64
from email.mime.text import MIMEText
from google_calendar import get_gmail_service

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Sends an email to a specific email address. This should only be called after a user has confirmed a draft.",
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

SAMPLE_PROMPTS = [
    "Yes, that looks good. Send it.",
    "Go ahead and send the email.",
    "Confirm and send."
]

def run(to: str, subject: str, body: str) -> str:
    """
    Sends an email to a specific email address. This should only be called after a user has confirmed a draft.
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
        
        # The 'me' keyword refers to the authenticated user's email address.
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": raw_message}
        
        send_message = (
            service.users().messages().send(userId="me", body=create_message).execute()
        )
        return f"Email sent successfully to {to}. Message ID: {send_message['id']}"

    except Exception as e:
        return f"An error occurred while sending email: {e}" 