import json
from datetime import datetime
import pytz
from duckduckgo_search import DDGS
from google_calendar import get_all_upcoming_events

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

# --- Tool and function definitions for OpenAI ---

# This is a dictionary of the functions that the LLM can call.
available_functions = {
    "get_current_time": get_current_time,
    "search_web": search_web,
    "get_all_upcoming_events": get_all_upcoming_events,
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
    }
] 