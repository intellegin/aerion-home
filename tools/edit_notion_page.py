"""
edit_notion_page.py

This tool edits an existing page in a Notion database by replacing its content.
"""
from __future__ import annotations
from notion_client import Client, APIResponseError
import notion_auth

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "edit_notion_page",
        "description": "Edits an existing Notion page by completely replacing all of its content blocks with new content.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The ID of the Notion page to edit."
                },
                "new_content": {
                    "type": "string",
                    "description": "The new text content that will replace the page's existing content."
                }
            },
            "required": ["page_id", "new_content"]
        }
    }
}

def _get_notion_client() -> Client | None:
    """Helper to load token and initialize the Notion client."""
    token_data = notion_auth.load_token()
    if not token_data or 'access_token' not in token_data:
        return None
    return Client(auth=token_data['access_token'])

def run(page_id: str, new_content: str) -> str:
    """
    Edits a Notion page. It first deletes all existing content (blocks) on the
    page and then adds the new content as a single paragraph block.
    """
    notion = _get_notion_client()
    if not notion:
        return "Error: Not authenticated with Notion. Please connect in Settings > Integrations."

    try:
        # Step 1: Get all current blocks on the page
        existing_blocks = notion.blocks.children.list(block_id=page_id)
        
        # Step 2: Delete all existing blocks
        for block in existing_blocks.get("results", []):
            notion.blocks.delete(block_id=block["id"])

        # Step 3: Add the new content as a new block
        notion.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": new_content}}]
                    }
                }
            ]
        )
        return f"Successfully edited page with ID: {page_id}."
        
    except APIResponseError as e:
        error_message = e.body.get('message', 'Unknown API error')
        return f"Error editing Notion page: {error_message}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 