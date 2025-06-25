import json
import base64
from email.mime.text import MIMEText
from datetime import datetime
import pytz
from duckduckgo_search import DDGS
from google_calendar import get_all_upcoming_events, get_people_service, get_gmail_service

def get_current_time(timezone: str) -> str:
    """
    Get the current time in a specific timezone.

    :param timezone: The timezone to get the current time for, e.g., 'America/New_York'.
    :return: A string representing the current time.
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return f"The current time in {timezone} is {current_time.strftime('%I:%M %p')}."
    except pytz.UnknownTimeZoneError:
        return "Sorry, I couldn't recognize that timezone. Please use a valid IANA timezone name (e.g., 'America/New_York')."
    except Exception as e:
        return f"An error occurred: {e}"

def search_web(query: str) -> str:
    """
    Searches the web using DuckDuckGo for a given query.

    :param query: The search query.
    :return: A JSON string containing the search results.
    """
    try:
        with DDGS() as ddgs:
            results = [r for _, r in zip(range(5), ddgs.text(query, region='wt-wt', safesearch='off', timelimit='y'))]
            if not results:
                return "No results found."
            # Just return the snippets for the LLM to process
            return json.dumps([{"snippet": result["body"]} for result in results])
    except Exception as e:
        return f"An error occurred during web search: {e}"

def search_contacts(name: str) -> str:
    """
    Searches Google Contacts for a person by name and returns their contact info.
    You will be prompted to grant permissions the first time this is run.
    """
    service = get_people_service()
    if not service:
        return "Could not connect to Google Contacts."

    try:
        results = (
            service.people()
            .searchContacts(query=name, readMask="names,emailAddresses")
            .execute()
        )
        
        people = results.get("results", [])

        if not people:
            return f"No contact found for '{name}'."

        contact_list = []
        for person_result in people:
            person = person_result.get("person", {})
            names = person.get("names", [{}])
            emails = person.get("emailAddresses", [{}])
            
            contact_list.append({
                "name": names[0].get("displayName", "N/A"),
                "email": emails[0].get("value", "N/A"),
            })
        
        return json.dumps(contact_list)
    except Exception as e:
        return f"An error occurred searching contacts: {e}"

def create_email_draft(contact_name: str, subject: str, body: str) -> str:
    """
    Finds a contact's email and prepares a draft.
    The AI should call this first, show the draft to the user for confirmation,
    and then call `send_email` upon confirmation.
    """
    print(f"Creating email draft for {contact_name}...")
    contact_json = search_contacts(contact_name)
    try:
        contacts = json.loads(contact_json)
        if not isinstance(contacts, list) or not contacts:
             return f"Could not find a contact named {contact_name} to draft an email to. Please check the name."
        
        # For simplicity, use the first result if multiple are found.
        recipient_email = contacts[0].get("email")
        recipient_name = contacts[0].get("name", contact_name)

        if not recipient_email or recipient_email == "N/A":
            return f"Found contact '{recipient_name}', but they do not have an email address."
    except (json.JSONDecodeError, IndexError):
        return contact_json

    draft = {
        "to": recipient_email,
        "subject": subject,
        "body": body,
    }
    print(f"Draft created for {recipient_name} ({recipient_email}).")
    return json.dumps(draft)

def send_email(to: str, subject: str, body: str) -> str:
    """
    Sends an email to a specific email address. This should only be called after a user has confirmed a draft.
    """
    service = get_gmail_service()
    if not service:
        return "Could not connect to Gmail API."

    try:
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

def save_email_draft(to: str, subject: str, body: str) -> str:
    """
    Saves a draft email in the user's Gmail account.
    """
    service = get_gmail_service()
    if not service:
        return "Could not connect to Gmail API."

    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"message": {"raw": raw_message}}
        
        draft = service.users().drafts().create(userId="me", body=create_message).execute()
        return f"Draft saved successfully. Draft ID: {draft['id']}"

    except Exception as e:
        return f"An error occurred while saving the draft: {e}"

# --- Tool and function definitions for OpenAI ---

# This is a dictionary of the functions that the LLM can call.
available_functions = {
    "get_current_time": get_current_time,
    "search_web": search_web,
    "get_all_upcoming_events": get_all_upcoming_events,
    "search_contacts": search_contacts,
    "send_email": send_email,
    "create_email_draft": create_email_draft,
    "save_email_draft": save_email_draft,
}

# This is a list of tool definitions that we will pass to the OpenAI API.
# It tells the model what functions it has available and what their parameters are.
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in a specific timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "The timezone, e.g., 'America/New_York'. Default to user's local timezone if not provided.",
                    }
                },
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information on a given topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_upcoming_events",
            "description": "Get a list of all upcoming events from all of the user's Google Calendars, sorted by time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results_per_calendar": {
                        "type": "integer",
                        "description": "The maximum number of events to return from each calendar. Defaults to 5.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_contacts",
            "description": "Search for a person in Google Contacts by their name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the person to search for.",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "create_email_draft",
            "description": "Looks up a person in Google Contacts and creates a draft email for them. The AI should generate a subject and body, show the user the draft, and wait for confirmation before calling `send_email`.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {
                        "type": "string",
                        "description": "The name of the contact to search for and email.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email. Should be generated by the AI based on the user's request.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The content/body of the email. Should be generated by the AI based on the user's request.",
                    }
                },
                "required": ["contact_name", "subject", "body"],
            },
        },
    },
    {
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
] 