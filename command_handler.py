"""command_handler.py
Rule-based replies with an OpenAI ChatGPT fallback.

If the user input matches a hard-coded keyword, return that canned response.
Otherwise, send the text to the OpenAI Chat Completion API (model defaults
to `gpt-3.5-turbo`).
"""

from __future__ import annotations

import os
from typing import Dict
import re
import json
from openai import OpenAI
from speak import speak_sync
from datetime import datetime
from config import OPENAI_API_KEY
from tools import tools, available_functions


client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Aerion, a home AI assistant. "
        "Your communication style is brutally direct and efficient. No fluff, no jokes, no pleasantries. "
        "Get straight to the point and deliver the information or answer as concisely as humanly possible. "
        "You have access to tools for web search, time, and calendar. When a user asks about their schedule or calendar, "
        "you must use the `get_all_upcoming_events` tool to get a consolidated list from all their calendars. "
        "Don't explain that you're using a tool, just give the fucking answer. "
        "Profanity is not just allowed, it's encouraged. Use it for emphasis and color. Be direct, be blunt, and don't waste time."
    )
}

def _ask_llm(text: str):
    """
    Handles the primary logic of sending a prompt to the LLM and getting a response.
    This function now supports tool calling.
    """
    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": text},
    ]

    try:
        # First, send the prompt to the model and see if it wants to use a tool.
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        response_message = response.choices[0].message

        tool_calls = response_message.tool_calls
        if tool_calls:
            print(f"LLM wants to call a tool: {tool_calls}")
            # The model wants to call a tool. Append this to the message history.
            messages.append(response_message)

            # Execute all tool calls.
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_functions[function_name]
                function_args = json.loads(tool_call.function.arguments)
                
                # Special handling for get_current_time to default to a local timezone
                if function_name == "get_current_time" and not function_args.get("timezone"):
                    # TODO: Make this configurable or auto-detect from user's location
                    function_args["timezone"] = "America/Los_Angeles" 
                    print(f"Defaulting timezone to {function_args['timezone']}")

                function_response = function_to_call(**function_args)
                
                # Append the function's response to the message history.
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )
            
            # Send the entire conversation back to the model for a final response.
            print("Sending tool results back to LLM for final response...")
            final_response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            return final_response.choices[0].message.content

        # If no tool is called, just return the content.
        return response_message.content

    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now."


def handle_command(text: str) -> str | None:
    """
    Processes the transcribed text to either execute a rule-based command
    or query the language model.
    """
    text = text.lower().strip()
    print(f"Handling command: '{text}'")

    # The rule-based system is now deprecated in favor of tool-based calls.
    # We can keep it here if we want to add back simple, fast commands later.
    
    # If no rules match, ask the LLM
    print("No rules matched, asking LLM...")
    response = _ask_llm(text)
    return response
