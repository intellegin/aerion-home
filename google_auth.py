import os
import json
from typing import Optional
from flask import session # Import session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Define the scopes for the Google APIs you want to access
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
]
SCOPES.sort() # Sort scopes to ensure consistent order
CREDENTIALS_FILE = 'credentials.json' # Still needed for local fallback

def get_google_flow(redirect_uri: str) -> Flow:
    """
    Creates a Google OAuth Flow object from an environment variable or a local file.
    """
    client_config = None
    creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')

    if creds_json_str:
        try:
            client_config = json.loads(creds_json_str)
        except json.JSONDecodeError:
            raise ValueError("Failed to parse GOOGLE_CREDENTIALS_JSON.")
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
    elif os.path.exists(CREDENTIALS_FILE):
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
    else:
        raise FileNotFoundError(
            f"Neither '{CREDENTIALS_FILE}' not found, nor 'GOOGLE_CREDENTIALS_JSON' env var set."
        )
    
    return flow

def get_auth_url(redirect_uri: str) -> str:
    """Generates the Google Authentication URL for the user to visit."""
    flow = get_google_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def process_auth_callback(code: str, redirect_uri: str) -> bool:
    """
    Processes the authentication callback from Google, fetches the token,
    and saves the credentials to the user's session.
    """
    try:
        flow = get_google_flow(redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Instead of saving to a file, save to the session cookie
        session['google_credentials'] = json.loads(creds.to_json())
        return True
    except Exception as e:
        print(f"Error processing auth callback: {e}")
        return False

def get_credentials() -> Optional[Credentials]:
    """
    Gets user credentials from the session.
    Refreshes the token if it's expired.
    """
    creds_info = session.get('google_credentials')
    if not creds_info:
        return None

    creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
    
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save the refreshed credentials back to the session
            session['google_credentials'] = json.loads(creds.to_json())
        except Exception as e:
            print(f"Error refreshing token: {e}")
            revoke_auth() # Clear the bad credentials from the session
            return None
            
    return creds

def get_auth_status() -> dict:
    """
    Checks the current authentication status and returns user info if available.
    """
    creds = get_credentials()
    if creds and creds.valid:
        try:
            service = build('oauth2', 'v2', credentials=creds, cache_discovery=False)
            user_info = service.userinfo().get().execute()
            return {
                "status": "authenticated",
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture")
            }
        except Exception as e:
            print(f"Error fetching user info: {e}")
            return {"status": "unauthenticated", "error": str(e)}
    return {"status": "unauthenticated"}

def revoke_auth() -> bool:
    """Revokes access by clearing the credentials from the session."""
    if 'google_credentials' in session:
        session.pop('google_credentials', None)
        return True
    return False 