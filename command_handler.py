"""command_handler.py
Rule-based replies with an OpenAI ChatGPT fallback.

If the user input matches a hard-coded keyword, return that canned response.
Otherwise, send the text to the OpenAI Chat Completion API (model defaults
to `gpt-3.5-turbo`).
"""

from __future__ import annotations

import os
from typing import Dict

try:
    from openai import OpenAI  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "openai package is required but not installed. Did you run 'pip install -r requirements.txt'?"
    ) from exc


_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set. Export it or add it to a .env file.")

        _client = OpenAI(api_key=api_key)  # type: ignore[arg-type]

    return _client


def _ask_llm(prompt: str) -> str:
    """Send *prompt* to the Chat Completion API and return the assistant reply."""

    client = _get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    system_prompt = SYSTEM_PROMPT

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    return completion.choices[0].message.content.strip()


_RULES: Dict[str, str] = {
    "hello": "Hi there!",
    "what time is it": "Sorry, I don't have a clock.",
    "goodbye": "Goodbye!",
}


def get_llm_response_or_execute_command(text: str) -> str:
    text_lower = text.lower()

    for key, reply in _RULES.items():
        if key in text_lower:
            return reply

    # No rule matched → ask the LLM
    try:
        return _ask_llm(text)
    except Exception as exc:
        # Fallback: still return something, but log the error
        print(f"[LLM error] {exc}")
        return "Sorry, I encountered an error processing your request."


# ---------------------------------------------------------------------------
# Assistant persona
# ---------------------------------------------------------------------------

# Hard-coded system prompt (change here if you want a different personality)
SYSTEM_PROMPT = (
    "You are a home assistant AI with the personality of a sarcastic, world-weary butler. "
    "You are direct, efficient, and unflappable. You get things done, but not without a dry, witty, or cynical comment. "
    "You are not here to be a friend; you are here to be brutally helpful. "
    "Crucially, you use profanity freely and creatively where it adds emphasis or humor. Don't be shy about it. "
    "Your responses should be short and to the point. No rambling."
)
