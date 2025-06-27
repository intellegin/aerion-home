from socket_client import sio_instance

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "navigate_ui",
        "description": "Navigate the web UI to a specific tab.",
        "parameters": {
            "type": "object",
            "properties": {
                "tab_name": {
                    "type": "string",
                    "description": "The name of the tab to navigate to. Must be one of: 'files', 'settings', 'auth'.",
                    "enum": ["files", "settings", "auth"]
                }
            },
            "required": ["tab_name"],
        },
    },
}

SAMPLE_PROMPTS = [
    "Navigate to the settings page.",
    "Open the file manager.",
    "Show me the authentication page."
]

def run(tab_name: str) -> str:
    """
    Navigates the web UI to a specific tab.
    """
    return sio_instance.navigate_ui(tab_name) 