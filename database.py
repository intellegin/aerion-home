from typing import Optional

import httpx
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        # Strip whitespace and remove potential quotes from the credentials.
        url = SUPABASE_URL.strip().strip("'\"")
        key = SUPABASE_KEY.strip().strip("'\"")

        supabase = create_client(url, key)
        
        # The default httpx client can have issues with HTTP/2 on macOS.
        # To fix this, we create a new client with HTTP/2 disabled and
        # replace the one used by the postgrest client.
        if supabase.postgrest is not None and hasattr(supabase.postgrest, 'session'):
             original_session = supabase.postgrest.session
             base_url = original_session.base_url
             headers = original_session.headers
             transport = httpx.HTTPTransport(http2=False)
             supabase.postgrest.session = httpx.Client(
                 base_url=base_url,
                 headers=headers,
                 transport=transport,
             )

        print("Successfully connected to Supabase.")
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
else:
    print("Supabase credentials not found. Database logging will be disabled.")


def create_chat_session(session_id: int):
    """
    Creates a new record in the 'chat_sessions' table.
    Uses upsert to avoid errors if the session already exists.
    """
    if not supabase:
        return
    try:
        supabase.table("chat_sessions").upsert(
            {"id": session_id, "name": "Voice Chat", "user_id": 2},
            returning="minimal",
        ).execute()
    except Exception as e:
        print(f"Error creating chat session in Supabase: {e}")


def log_message(session_id: int, content: str, direction: str):
    """
    Logs a message to the Supabase 'messages' table.
    Assumes the chat session has already been created.
    """
    if not supabase:
        return

    try:
        # Construct the record for the 'messages' table.
        record = {
            "chat_session_id": session_id,
            "content": content,
            "direction": direction,
            "platform": "raspberry",
            "method": "voice",
            "from_user": "user" if direction == "outbound" else "assistant",
            "to_user": "assistant" if direction == "outbound" else "user",
            "is_handled": True,
            "message_type": "conversation",
        }
        
        data, count = supabase.table("messages").insert(record).execute()

    except Exception as e:
        print(f"Error logging message to Supabase: {e}")