import os
import importlib.util
import json

# --- Globals to hold the loaded tools ---
tools = []
available_functions = {}
sample_prompts = [] # This will be deprecated
grouped_prompts = {}

def _load_tools():
    """
    Dynamically loads tools from the 'tools' directory, skipping __init__.py.
    Each tool file is expected to have:
    - TOOL_DEFINITION: A dictionary defining the tool for the OpenAI API.
    - run: The function to be executed for the tool.
    - TOOL_CATEGORY (optional): A string for grouping in the UI.
    - SAMPLE_PROMPTS (optional): A list of example prompts.
    """
    global tools, available_functions, grouped_prompts
    
    # Clear existing loaded tools to allow for reloading
    tools = []
    available_functions = {}
    grouped_prompts = {}

    tools_dir = os.path.dirname(__file__)
    
    for filename in os.listdir(tools_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            module_name = filename[:-3]
            module_path = os.path.join(tools_dir, filename)
            
            try:
                # Import the module
                spec = importlib.util.spec_from_file_location(f"tools.{module_name}", module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Get the tool definition and the runnable function
                    if hasattr(module, 'TOOL_DEFINITION') and hasattr(module, 'run'):
                        tool_def = module.TOOL_DEFINITION
                        
                        # Add sample prompts to the grouped dictionary if they exist
                        if hasattr(module, 'SAMPLE_PROMPTS'):
                            category = getattr(module, 'TOOL_CATEGORY', 'Uncategorized')
                            if category not in grouped_prompts:
                                grouped_prompts[category] = []
                            grouped_prompts[category].extend(module.SAMPLE_PROMPTS)

                        # Ensure function name matches definition
                        func_name = tool_def.get("function", {}).get("name")
                        if not func_name:
                            print(f"Warning: Tool definition in '{filename}' is missing a function name.")
                            continue

                        tools.append(tool_def)
                        available_functions[func_name] = module.run
                        print(f"Successfully loaded tool: {func_name}")
                    else:
                        print(f"Warning: Tool file '{filename}' is missing TOOL_DEFINITION or run function.")

            except Exception as e:
                print(f"Error loading tool from {filename}: {e}")

# Load tools when the package is imported
_load_tools() 