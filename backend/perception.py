"""
Perception module — extracts structured intent, entities, and tool hints
from user input using the Gemini LLM.

This is the first step in the agent loop:
  perception → memory → decision → action
"""

import os
import re
import datetime
import logging
from typing import Optional, List
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()
log = logging.getLogger("email-assistant.perception")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class PerceptionResult(BaseModel):
    user_input: str
    intent: Optional[str] = None
    entities: List[str] = []
    tool_hint: Optional[str] = None
    time_refs: List[str] = []


def extract_perception(user_input: str) -> PerceptionResult:
    """Extract intent, entities, and tool hints from user input using LLM."""

    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""You are an AI that extracts structured information from user input about emails and calendar.
Today's date is {today}.

Input: "{user_input}"

Return a Python dictionary with these keys:
- intent: one of [read_email, search_email, thread_summary, attachment_document, document_query, write_email, read_calendar, write_calendar, free_slots, general]
- entities: list of key strings (names, dates, topics, email addresses)
- tool_hint: the most likely MCP tool name, one of [get_unread_emails_today, get_emails_by_date_range, search_emails, get_email_thread, get_email_attachments, search_indexed_documents, send_email, get_todays_events, get_events_for_date, check_free_slots, create_event] or null
- time_refs: list of any time references found (e.g. ["today", "last week", "Feb 5th"])

Output ONLY the dictionary on a single line. No markdown, no backticks, no explanation.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        log.info("Perception LLM output: %s", raw)

        # Strip markdown if present
        clean = re.sub(r"^```(?:json|python)?|```$", "", raw, flags=re.MULTILINE).strip()

        parsed = eval(clean)  # safe here — LLM output is a dict literal

        # Fix common issue: entities returned as dict instead of list
        if isinstance(parsed.get("entities"), dict):
            parsed["entities"] = list(parsed["entities"].values())

        return PerceptionResult(user_input=user_input, **parsed)

    except Exception as e:
        log.warning("Perception extraction failed: %s", e)
        return PerceptionResult(user_input=user_input, intent="general")
