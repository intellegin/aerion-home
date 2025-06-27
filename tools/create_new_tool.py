import os
import json

TOOL_CATEGORY = "System"

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "create_new_tool",
        "description": "Creates a new tool file from a given name, Python code, and JSON tool definition. This allows the assistant to create new capabilities for itself.",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "The snake_case name of the tool, without the .py extension (e.g., 'get_weather'). This will be the filename."
                },
                "tool_code": {
                    "type": "string",
                    "description": "A string containing the complete, runnable Python code for the tool's 'run' function, including any necessary imports."
                },
                "tool_definition_json": {
                    "type": "string",
                    "description": "A JSON string of the OpenAI tool definition dictionary. The 'name' in the function definition must match the 'tool_name'."
                }
            },
            "required": ["tool_name", "tool_code", "tool_definition_json"]
        }
    }
}

SAMPLE_PROMPTS = [
    "Create a new tool named 'tell_joke' that tells a random joke.",
    "Make a tool that can fetch the current weather for a given city.",
    "Generate a tool file to get the top stories from Hacker News."
]

def run(tool_name: str, tool_code: str, tool_definition_json: str) -> str:
    """
    Creates a new Python file for a tool in the 'tools' directory.
    """
    if not tool_name.isidentifier() or not tool_name.islower():
        return "Error: Tool name must be a valid, lowercase Python identifier (snake_case)."
    
    # Validate the JSON definition
    try:
        tool_def = json.loads(tool_definition_json)
        if not isinstance(tool_def, dict):
            raise ValueError("Tool definition must be a JSON object.")
        if tool_def.get("function", {}).get("name") != tool_name:
            return f"Error: The function name in the JSON definition ('{tool_def.get('function', {}).get('name')}') does not match the tool_name ('{tool_name}')."
    except (json.JSONDecodeError, ValueError) as e:
        return f"Error: Invalid JSON for tool definition. {e}"

    # Construct the full file content
    file_content = f"""
# --- Imports and setup for the new tool ---
{tool_code}

# --- Tool Definition ---
TOOL_DEFINITION = {json.dumps(tool_def, indent=4)}
"""
    
    file_path = os.path.join(os.path.dirname(__file__), f"{tool_name}.py")
    
    try:
        with open(file_path, 'w') as f:
            f.write(file_content)
        return f"Successfully created new tool: '{tool_name}'. The system will now reload to activate it."
    except Exception as e:
        return f"An error occurred while creating the tool file: {e}" 