import datetime
import os.path
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_google_service(service_name: str, version: str):
    """
    Generic function to authenticate with a Google API and return a service object.
    Handles the OAuth 2.0 flow and token management.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "credentials.json not found. Please follow the setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    try:
        service = build(service_name, version, credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def get_calendar_service():
    """Returns an authenticated Google Calendar service object."""
    return get_google_service("calendar", "v3")

def get_people_service():
    """Returns an authenticated Google People service object."""
    return get_google_service("people", "v1")

def get_gmail_service():
    """Returns an authenticated Gmail service object."""
    return get_google_service("gmail", "v1")

def list_calendars():
    """Lists all the user's calendars."""
    service = get_calendar_service()
    if not service:
        return "Could not connect to Google Calendar."
    
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])
        if not calendars:
            return "No calendars found."
        
        # Format for the LLM
        return json.dumps(
            [{"summary": cal["summary"], "id": cal["id"]} for cal in calendars]
        )
    except HttpError as error:
        return f"An error occurred: {error}"

def get_upcoming_events(max_results=10, calendar_id="primary"):
    """
    Lists the next `max_results` upcoming events from a specific calendar.
    
    :param calendar_id: The ID of the calendar to query. Defaults to 'primary'.
    """
    service = get_calendar_service()
    if not service:
        return "Could not connect to Google Calendar."
        
    now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
    print(f"Getting upcoming {max_results} events")
    try:
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found."
        
        # Format the events for the LLM
        event_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            event_list.append({
                "summary": event["summary"],
                "start": start
            })

        return json.dumps(event_list)

    except HttpError as error:
        return f"An error occurred: {error}"

def get_all_upcoming_events(max_results_per_calendar=5):
    """
    Fetches upcoming events from all available calendars, combines them, and sorts them.
    """
    service = get_calendar_service()
    if not service:
        return "Could not connect to Google Calendar."

    try:
        # 1. Get list of all calendars
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])
        if not calendars:
            return "No calendars found."

        all_events = []
        now = datetime.datetime.utcnow().isoformat() + "Z"

        # 2. Loop through each calendar and get events
        for cal in calendars:
            calendar_id = cal["id"]
            calendar_summary = cal["summary"]
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=max_results_per_calendar,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            for event in events:
                # Add calendar info to each event for context
                event["calendar_summary"] = calendar_summary
                all_events.append(event)

        if not all_events:
            return "No upcoming events found across all calendars."

        # 3. Sort all collected events by start time
        all_events.sort(key=lambda x: x["start"].get("dateTime", x["start"].get("date")))

        # 4. Format for the LLM
        event_list = []
        for event in all_events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            event_list.append({
                "summary": event["summary"],
                "start": start,
                "calendar": event["calendar_summary"]
            })

        return json.dumps(event_list)

    except HttpError as error:
        return f"An error occurred: {error}" 