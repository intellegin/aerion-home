import json
from duckduckgo_search import DDGS

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for information on a given topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
}

def run(query: str) -> str:
    """
    Searches the web using DuckDuckGo for a given query.

    :param query: The search query.
    :return: A JSON string containing the search results.
    """
    try:
        with DDGS() as ddgs:
            results = [r for _, r in zip(range(5), ddgs.text(query, region='wt-wt', safesearch='off', timelimit='y'))]
            if not results:
                return "No results found."
            # Just return the snippets for the LLM to process
            return json.dumps([{"snippet": result["body"]} for result in results])
    except Exception as e:
        return f"An error occurred during web search: {e}" 