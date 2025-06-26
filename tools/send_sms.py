"""
send_sms.py

A tool for sending SMS messages using the Twilio API.

This tool requires the following environment variables to be set:
- TWILIO_ACCOUNT_SID: Your Twilio Account SID.
- TWILIO_AUTH_TOKEN: Your Twilio Auth Token.
- TWILIO_PHONE_NUMBER: Your Twilio phone number.
"""
from __future__ import annotations

import os
from twilio.rest import Client

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_sms",
        "description": "Sends an SMS message to a specified phone number using Twilio.",
        "parameters": {
            "type": "object",
            "properties": {
                "to_number": {
                    "type": "string",
                    "description": "The recipient's phone number in E.164 format (e.g., '+14155552671').",
                },
                "message": {
                    "type": "string",
                    "description": "The text content of the SMS message.",
                }
            },
            "required": ["to_number", "message"],
        },
    },
}

def run(to_number: str, message: str) -> str:
    """
    Sends an SMS message using Twilio.

    Args:
        to_number: The recipient's phone number in E.164 format (e.g., "+14155552671").
        message: The text content of the message.

    Returns:
        A string indicating the result of the operation.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, twilio_phone_number]):
        return "Twilio credentials are not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables."

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            to=to_number,
            from_=twilio_phone_number,
            body=message
        )
        return f"Message sent successfully to {to_number}. SID: {message.sid}"
    except Exception as e:
        return f"Failed to send SMS: {e}" 