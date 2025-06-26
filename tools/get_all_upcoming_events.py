import json
from typing import Union
from google_calendar import get_all_upcoming_events as fetch_events

def _get_user_timezone() -> Union[str, None]:
    """Reads the user's configured timezone from settings.json."""
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        return settings.get("timezone")
    except (FileNotFoundError, json.JSONDecodeError):
        return None

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_all_upcoming_events",
        "description": "Get a consolidated list of all upcoming events from all of the user's Google Calendars, sorted by time. This is the primary tool for checking a user's schedule.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results_per_calendar": {
                    "type": "integer",
                    "description": "Maximum number of events to return per calendar. Defaults to 5.",
                    "default": 5
                }
            },
            "required": []
        }
    },
}

def run(max_results_per_calendar: int = 5) -> str:
    """
    Fetches all upcoming events from the user's calendars.
    Automatically uses the timezone configured in the user's settings.
    """
    user_timezone = _get_user_timezone()
    return fetch_events(
        max_results_per_calendar=max_results_per_calendar, 
        timezone=user_timezone
    ) 