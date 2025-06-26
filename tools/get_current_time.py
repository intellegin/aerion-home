from datetime import datetime
import pytz

TOOL_DEFINITION = {
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
}

def run(timezone: str) -> str:
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