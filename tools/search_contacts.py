import json
from google_calendar import get_people_service
from thefuzz import process

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_contacts",
        "description": "Search for a person in Google Contacts by their name. Do not reveal contact details unless the user explicitly asks for them.",
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
}

def run(name: str) -> str:
    """
    Searches all of the user's Google Contacts for a person by name and returns their contact info.
    Uses fuzzy matching to find the best result, even with misspellings.
    """
    service = get_people_service()
    if not service:
        return "Could not connect to Google Contacts."

    try:
        # Get all connections (contacts)
        all_people = []
        page_token = None
        while True:
            results = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    personFields="names,emailAddresses,phoneNumbers",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            all_people.extend(results.get("connections", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        
        if not all_people:
            return "No contacts found in your Google account."

        # Create a dictionary of {displayName: person_object}
        contacts_dict = {}
        for person in all_people:
            names = person.get("names", [{}])
            if names and names[0].get("displayName"):
                display_name = names[0]["displayName"]
                contacts_dict[display_name] = person
        
        if not contacts_dict:
            return "Could not find any contacts with names in your account."

        # Use thefuzz to find the best match from the dictionary keys (the names)
        best_match_name, score = process.extractOne(name, contacts_dict.keys())
        
        if score < 70: # You can adjust this threshold
             return f"No close contact match found for '{name}'. Best guess was '{best_match_name}', but the confidence score ({score}) was too low."

        best_match_person = contacts_dict[best_match_name]
        
        email = best_match_person.get("emailAddresses", [{}])[0].get("value", "N/A")
        phone = best_match_person.get("phoneNumbers", [{}])[0].get("value", "N/A")

        return json.dumps({
            "name": best_match_name,
            "email": email,
            "phone": phone,
            "resourceName": best_match_person.get("resourceName")
        })

    except Exception as e:
        return f"An error occurred searching contacts: {e}" 