import json
from google_calendar import get_people_service

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_my_profile",
        "description": "Get the user's own profile information, such as their name and email address. Do not reveal this information unless explicitly asked.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

SAMPLE_PROMPTS = [
    "Who am I?",
    "What's my name?",
    "What is my email address?"
]

def run() -> str:
    """
    Fetches the user's own Google profile information (name and email).
    """
    service = get_people_service()
    if not service:
        return "Could not connect to Google People API."
    try:
        profile = service.people().get(
            resourceName='people/me',
            personFields='names,emailAddresses'
        ).execute()
        name = profile.get('names', [{}])[0].get('displayName', 'N/A')
        email = profile.get('emailAddresses', [{}])[0].get('value', 'N/A')
        return json.dumps({"name": name, "email": email})
    except Exception as e:
        return f"An error occurred while fetching your profile: {e}" 