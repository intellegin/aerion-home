"""
search_notion_databases.py

This tool searches for databases in a user's Notion workspace.
"""
from __future__ import annotations
from notion_client import Client, APIResponseError
import notion_auth

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_notion_databases",
        "description": "Searches for databases in your Notion workspace that have been shared with the integration. Helps find the database_id needed for other functions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "An optional search query to filter databases by title."
                }
            },
            "required": []
        }
    }
}

SAMPLE_PROMPTS = [
    "Search for a Notion database named 'Tasks'.",
    "What databases can you find in my Notion?",
    "Find all databases related to 'Meeting Notes'."
]

def _get_notion_client() -> Client | None:
    """Helper to load token and initialize the Notion client."""
    token_data = notion_auth.load_token()
    if not token_data or 'access_token' not in token_data:
        return None
    return Client(auth=token_data['access_token'])

def run(query: str = None) -> str:
    """
    Searches for databases in your Notion workspace.
    To use this, you must first share specific databases with your integration
    in the Notion UI (via the Share menu).
    """
    notion = _get_notion_client()
    if not notion:
        return "Error: Not authenticated with Notion. Please connect in Settings > Integrations."

    try:
        search_params = {"filter": {"value": "database", "property": "object"}}
        if query:
            search_params["query"] = query
        
        response = notion.search(**search_params)
        databases = response.get("results")

        if not databases:
            return "No databases found. Make sure you have shared specific databases with this integration in Notion's 'Share' menu."

        formatted_list = []
        for db in databases:
            db_id = db.get("id")
            title_list = db.get("title", [])
            title = "".join([t.get("plain_text", "") for t in title_list]) if title_list else "Untitled"
            formatted_list.append(f"- {title} (ID: {db_id})")

        return "Found the following databases:\\n" + "\\n".join(formatted_list)
    except APIResponseError as e:
        return f"Error searching Notion databases: {e.body.get('message', 'Unknown API error')}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 