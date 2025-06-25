"""command_handler.py
Rule-based replies with an OpenAI ChatGPT fallback.

If the user input matches a hard-coded keyword, return that canned response.
Otherwise, send the text to the OpenAI Chat Completion API (model defaults
to `gpt-3.5-turbo`).
"""

from __future__ import annotations

import os
from typing import Dict, List
import re
import json
from openai import OpenAI
from speak import speak_sync
from datetime import datetime
from config import OPENAI_API_KEY
from tools import tools, available_functions


class RestartRequest(Exception):
    """Custom exception to signal a user-requested restart."""
    pass


client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are a home AI assistant. "
        "Your communication style is brutally direct and efficient. No fluff, no pleasantries. "
        "Get straight to the point and deliver the information or answer as concisely as humanly possible. "
        "You have access to tools for web search, time, and calendar. When a user asks about their schedule or calendar, "
        "you must use the `get_all_upcoming_events` tool to get a consolidated list from all their calendars. "
        
        "You can search Google Contacts and get your own profile information. You do not have permission to create, update, or delete contacts."

        "You can also control the web interface. Use the `navigate_ui` tool to switch between the 'files', 'settings', and 'auth' tabs when the user asks."

        "EMAIL WORKFLOW: When asked to send an email, you must follow this exact, multi-turn conversational sequence: "
        "1. IDENTIFY RECIPIENT: The user will say something like 'send an email to [name]'. First, find the contact using `search_contacts`. If you can't find them, report it and stop. If you find them, immediately ask the user 'What should the email say?' and then stop and wait for their response. "
        "2. GET CONTENT & CREATE DRAFT: The user will provide the body of the message. Once they have, you must generate an appropriate subject line and call `create_email_draft` with the contact name, your generated subject, and the user's provided body. "
        "3. CONFIRM & ITERATE: After creating the draft, you MUST present it to the user: 'I have a draft for [Name] at [email]. Subject: [Subject]. Body: [Body]. Does that look right, or do you want to make any changes?'. "
        "4. HANDLE UPDATES: If the user wants to change something (e.g., 'change the subject'), update the draft by calling `create_email_draft` again with the new information. Then, go back to step 3 and present the new draft for confirmation. Repeat this loop until the user is satisfied. "
        "5. SEND OR SAVE: If the user confirms the draft is correct ('yes, send it'), you MUST call the `send_email` tool with the confirmed `to`, `subject`, and `body`. If the user says to 'cancel' or 'save for later', you MUST call the `save_email_draft` tool. "

        "Don't explain your steps. Just execute the workflow. "
        "Profanity is not just allowed, it's encouraged. Use it for emphasis and color. Be direct, be blunt, and don't waste time."
    )
}

def _ask_llm(messages: List[Dict[str, str]]):
    """
    Handles the primary logic of sending a prompt to the LLM and getting a response.
    This function now supports tool calling and maintains conversation history.
    """
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
            # The model wants to call a tool. Append its response to the message history.
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
            # Append the final response to the history before returning
            messages.append(final_response.choices[0].message)
            return final_response.choices[0].message.content

        # If no tool is called, just return the content.
        # Append the response to the history as well
        messages.append(response_message)
        return response_message.content

    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now."


def handle_command(text: str, history: List[Dict[str, str]]) -> str | None:
    """
    Processes the transcribed text, maintaining conversation history.
    First checks for special hard-coded commands like 'restart'.
    """
    normalized_text = text.strip().lower()
    if normalized_text in ("restart", "restart yourself", "restart the system", "system restart"):
        print("💡 User requested restart.")
        raise RestartRequest()

    # Append the new user message to the history
    history.append({"role": "user", "content": text})
    
    print(f"Handling command: '{text}'")
    
    # Pass the entire history to the LLM
    response = _ask_llm(history)
    return response
