"""
get_page_content.py

This tool retrieves the text content of a Notion page.
"""
from __future__ import annotations
from notion_client import Client, APIResponseError
import notion_auth

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_page_content",
        "description": "Retrieves all the text content from a specified Notion page.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the Notion page to read."
                }
            },
            "required": ["page_id"]
        }
    }
}

def _get_notion_client() -> Client | None:
    """Helper to load token and initialize the Notion client."""
    token_data = notion_auth.load_token()
    if not token_data or 'access_token' not in token_data:
        return None
    return Client(auth=token_data['access_token'])

def run(page_id: str) -> str:
    """
    Retrieves and concatenates all text from the content blocks of a Notion page.
    """
    notion = _get_notion_client()
    if not notion:
        return "Error: Not authenticated with Notion. Please connect in Settings > Integrations."

    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        
        full_text = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in block and "rich_text" in block[block_type]:
                for rich_text_item in block[block_type]["rich_text"]:
                    if "plain_text" in rich_text_item:
                        full_text.append(rich_text_item["plain_text"])
        
        if not full_text:
            return f"Page with ID {page_id} was found, but it contains no readable text content."

        return "\\n".join(full_text)

    except APIResponseError as e:
        return f"Error getting page content: {e.body.get('message', 'Unknown API error')}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 