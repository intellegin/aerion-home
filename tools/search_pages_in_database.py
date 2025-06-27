"""
search_pages_in_database.py

This tool searches for pages within a specific Notion database.
"""
from __future__ import annotations
from notion_client import Client, APIResponseError
import notion_auth

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_pages_in_database",
        "description": "Searches for pages within a specific Notion database based on a query.",
        "parameters": {
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "The ID of the Notion database to search within."
                },
                "query": {
                    "type": "string",
                    "description": "The search query to find pages by title or content."
                }
            },
            "required": ["database_id", "query"]
        }
    }
}

SAMPLE_PROMPTS = [
    "In the 'Tasks' database, search for pages about 'marketing'.",
    "Find pages related to 'Q3 planning' in the database with ID 'xyz-123'.",
    "Look for a page titled 'Project Phoenix' in my 'Projects' database."
]

def _get_notion_client() -> Client | None:
    """Helper to load token and initialize the Notion client."""
    token_data = notion_auth.load_token()
    if not token_data or 'access_token' not in token_data:
        return None
    return Client(auth=token_data['access_token'])

def run(database_id: str, query: str) -> str:
    """
    Searches for pages within a specific Notion database using a query.
    """
    notion = _get_notion_client()
    if not notion:
        return "Error: Not authenticated with Notion. Please connect in Settings > Integrations."

    try:
        response = notion.databases.query(database_id=database_id, query=query)
        pages = response.get("results")

        if not pages:
            return f"No pages found in database {database_id} matching query '{query}'."

        formatted_list = []
        for page in pages:
            page_id = page.get("id")
            properties = page.get("properties", {})
            
            # Find the title property
            title_prop_name = next((name for name, prop in properties.items() if prop['type'] == 'title'), None)
            title_list = properties[title_prop_name].get("title", []) if title_prop_name else []
            
            title = "".join([t.get("plain_text", "") for t in title_list]) if title_list else "Untitled"
            formatted_list.append(f"- {title} (ID: {page_id})")

        return "Found the following pages:\\n" + "\\n".join(formatted_list)
    except APIResponseError as e:
        return f"Error searching pages in database: {e.body.get('message', 'Unknown API error')}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 