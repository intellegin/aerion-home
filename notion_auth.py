"""
notion_auth.py

Handles the Notion OAuth 2.0 flow and provides helper functions
for managing Notion API access.
"""
from __future__ import annotations

import os
import json
import requests
from urllib.parse import urlencode

# --- Constants ---
NOTION_TOKEN_FILE = 'notion_token.json'
NOTION_API_BASE_URL = 'https://api.notion.com/v1'
NOTION_OAUTH_URL = 'https://api.notion.com/v1/oauth/authorize'
NOTION_TOKEN_URL = 'https://api.notion.com/v1/oauth/token'

def get_auth_url() -> str:
    """Generates the Notion authorization URL."""
    client_id = os.environ.get('NOTION_CLIENT_ID')
    if not client_id:
        raise ValueError("NOTION_CLIENT_ID is not set in environment variables.")
    
    # Use the base URL from the environment, falling back to localhost for safety
    base_url = os.environ.get('FLASK_BASE_URL', 'http://127.0.0.1:5001')
    redirect_uri = f"{base_url}/notion/callback"

    params = {
        "client_id": client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": redirect_uri
    }
    return f"{NOTION_OAUTH_URL}?{urlencode(params)}"

def handle_callback(code: str) -> bool:
    """
    Handles the callback from Notion, exchanges the code for a token,
    and saves the token.
    """
    client_id = os.environ.get('NOTION_CLIENT_ID')
    client_secret = os.environ.get('NOTION_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("Error: NOTION_CLIENT_ID or NOTION_CLIENT_SECRET not set.")
        return False

    base_url = os.environ.get('FLASK_BASE_URL', 'http://127.0.0.1:5001')
    redirect_uri = f"{base_url}/notion/callback"

    response = requests.post(
        NOTION_TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )

    if response.status_code == 200:
        save_token(response.json())
        print("Successfully authenticated with Notion and saved token.")
        return True
    else:
        print(f"Error authenticating with Notion: {response.status_code} - {response.text}")
        return False

def save_token(token_data: dict):
    """Saves the Notion token data to a file."""
    with open(NOTION_TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)

def load_token() -> dict | None:
    """Loads the Notion token from a file."""
    if not os.path.exists(NOTION_TOKEN_FILE):
        return None
    try:
        with open(NOTION_TOKEN_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None

def get_auth_status() -> dict:
    """Checks if a valid Notion token exists and returns the auth status."""
    token = load_token()
    if token and 'access_token' in token:
        return {
            "status": "authenticated",
            "workspace_name": token.get("workspace_name", "Unknown Workspace")
        }
    return {"status": "unauthenticated"}

def revoke_access():
    """Deletes the local Notion token file."""
    if os.path.exists(NOTION_TOKEN_FILE):
        os.remove(NOTION_TOKEN_FILE)
        print("Notion access token revoked.")
    else:
        print("No Notion access token found to revoke.") 