"""
create_notion_page.py

This tool creates a new page in a Notion database.
"""
from __future__ import annotations
from notion_client import Client, APIResponseError
import notion_auth

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "create_notion_page",
        "description": "Creates a new page with a title and content in a specified Notion database.",
        "parameters": {
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "The ID of the Notion database where the page will be created. Use the search_notion_databases function to find this."
                },
                "page_title": {
                    "type": "string",
                    "description": "The title of the new page to create."
                },
                "content": {
                    "type": "string",
                    "description": "The text content to be placed in a paragraph block on the new page."
                }
            },
            "required": ["database_id", "page_title", "content"]
        }
    }
}

SAMPLE_PROMPTS = [
    "Create a new page in the 'Meeting Notes' database with the title 'Project Kickoff' and content 'We discussed the project timeline and goals.'",
    "Add a page to my 'Ideas' database. Title it 'New App Idea' and write down 'A mobile app that tracks water intake.'",
    "In my database with ID 'xyz-123', create a page titled 'Book Summary: The Great Gatsby' and add the key plot points as content."
]

def _get_notion_client() -> Client | None:
    """Helper to load token and initialize the Notion client."""
    token_data = notion_auth.load_token()
    if not token_data or 'access_token' not in token_data:
        return None
    return Client(auth=token_data['access_token'])

def run(database_id: str, page_title: str, content: str) -> str:
    """
    Creates a new page in a specific Notion database. You can find the
    database_id by using the `search_notion_databases` function.
    """
    notion = _get_notion_client()
    if not notion:
        return "Error: Not authenticated with Notion. Please connect in Settings > Integrations."

    try:
        new_page_data = {
            "parent": {"database_id": database_id},
            "properties": {
                "title": { # Assumes the title property is named "title" or "Name"
                    "title": [{"text": {"content": page_title}}]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                }
            ]
        }
        
        # Check database properties to find the correct title property name
        db_info = notion.databases.retrieve(database_id)
        title_prop_name = None
        for prop_name, prop_details in db_info['properties'].items():
            if prop_details['type'] == 'title':
                title_prop_name = prop_name
                break
        
        if not title_prop_name:
             return f"Error: Could not find a 'title' property in the database {database_id}. Cannot set page title."

        # Adjust the payload to use the correct property name
        if title_prop_name != 'title':
            new_page_data['properties'][title_prop_name] = new_page_data['properties'].pop('title')

        created_page = notion.pages.create(**new_page_data)
        page_url = created_page.get("url")
        return f"Successfully created Notion page: '{page_title}'. URL: {page_url}"
    except APIResponseError as e:
        error_message = e.body.get('message', 'Unknown API error')
        if "Could not find a database with ID" in error_message:
            return f"Error: Database with ID '{database_id}' not found. Please check the ID and ensure the integration has access to it."
        if "is not a valid" in error_message:
             return f"Error: The database schema might be incompatible. {error_message}"
        return f"Error creating Notion page: {error_message}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 