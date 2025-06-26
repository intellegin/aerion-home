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
from tzlocal import get_localzone_name
from zoneinfo import ZoneInfoNotFoundError, ZoneInfo
import importlib


class RestartRequest(Exception):
    """Custom exception to signal a user-requested restart."""
    pass


client = OpenAI(api_key=OPENAI_API_KEY)
conversation_history = []
is_speaking = False
is_listening = False
assistant_state = "idle" # idle, listening, processing, speaking, waiting_for_response


def get_system_prompt() -> Dict[str, str]:
    """
    Creates the system prompt, injecting the user's configured timezone if available.
    """
    # Base prompt content
    content = (
        "You are a home AI assistant. "
        "Your communication style is brutally direct and efficient. No fluff, no pleasantries. "
        "Get straight to the point and deliver the information or answer as concisely as humanly possible. "
        "You have access to tools for web search, time, and calendar. When a user asks about their schedule or calendar, "
        "you must use the `get_all_upcoming_events` tool to get a consolidated list from all their calendars. "
        
        "You can search Google Contacts and get your own profile information. You do not have permission to create, update, or delete contacts."

        "TOOL CREATION: You have the ability to create new tools for yourself. When a user asks for a capability you don't have, you must use the `create_new_tool` function. You will need to provide three arguments: `tool_name` (a lowercase, snake_case string), `tool_code` (the full Python code for the 'run' function, including imports), and `tool_definition_json` (the JSON definition for the tool). For example, to create a tool to get the weather, you would call `create_new_tool` with `tool_name='get_weather'`, `tool_code='import requests\\n\\ndef run(city: str):\\n    # ...code to get weather...'`, and a complete `tool_definition_json` string. After creating a tool, inform the user that it will be available after a reload."

        "CONFIDENTIALITY: When you use tools that return personal information like phone numbers or email addresses (from `search_contacts` or `get_my_profile`), you MUST NOT include this information in your response. Simply confirm you found the contact (e.g., 'Found him.' or 'I found a contact for John Smith.'). Only provide specific details if the user explicitly asks for them (e.g., 'what is his phone number?'). The only exception is for disambiguation; if you find multiple contacts for the same name, you may use minimal information (like an email) to ask for clarification."

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

    # Try to read the timezone from settings.json, fallback to auto-detect
    user_timezone = None
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        user_timezone = settings.get("timezone")
        if user_timezone:
            print(f"Using timezone from settings: {user_timezone}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # File doesn't exist or is empty, will try auto-detect

    if not user_timezone:
        try:
            user_timezone = get_localzone_name()
            print(f"Auto-detected system timezone: {user_timezone}")
        except ZoneInfoNotFoundError:
            print("Warning: Could not auto-detect timezone. Please set it manually in settings.")

    if user_timezone:
        content += f" The user's timezone is {user_timezone}. All date and time related queries should be interpreted and responded to in this timezone."
        print(f"System prompt updated with timezone: {user_timezone}")


    return {"role": "system", "content": content}

SYSTEM_PROMPT = get_system_prompt()


def _get_user_timezone() -> str | None:
    """
    Reads the user's configured timezone from settings.json,
    falling back to auto-detection if not present.
    """
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        configured_timezone = settings.get("timezone")
        if configured_timezone:
            return configured_timezone
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # Fallback to auto-detect

    try:
        return get_localzone_name()
    except ZoneInfoNotFoundError:
        return None

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
                
                # If the function is get_current_time and no timezone is specified,
                # use the one from the user's settings.
                if function_name == "get_current_time" and not function_args.get("timezone"):
                    user_timezone = _get_user_timezone()
                    if user_timezone:
                        function_args["timezone"] = user_timezone
                        print(f"Using configured timezone for get_current_time: {user_timezone}")

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
