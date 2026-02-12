"""
Decision module — generates a plan (FUNCTION_CALL or FINAL_ANSWER) based on
perception, memory, and available tool descriptions.

This is the third step in the agent loop:
  perception → memory → decision → action
"""

import os
import datetime
import logging
from typing import List, Optional
from dotenv import load_dotenv
from google import genai

from perception import PerceptionResult
from memory import MemoryItem

load_dotenv()
log = logging.getLogger("email-assistant.decision")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_plan(
    perception: PerceptionResult,
    memory_items: List[MemoryItem],
    tool_descriptions: str,
    iteration_context: str = "",
) -> str:
    """
    Generate a plan using Gemini based on perception + memory + tools.
    Returns a single line: FUNCTION_CALL: ... or FINAL_ANSWER: ...
    """

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    memory_text = (
        "\n".join(f"- [{m.type}] {m.text[:300]}" for m in memory_items)
        if memory_items
        else "No relevant memories."
    )

    system_prompt = f"""You are a smart personal assistant that manages the user's Gmail inbox and Google Calendar. Today's date is {today_str}.

Available tools:
{tool_descriptions}

You must respond with EXACTLY ONE line in one of these formats (no additional text):
1. For function calls:
   FUNCTION_CALL: function_name|param1|param2|...

2. For final answers (a human-readable response to the user):
   FINAL_ANSWER: [your response text here]

PERCEPTION SUMMARY:
- User said: "{perception.user_input}"
- Intent: {perception.intent}
- Entities: {', '.join(perception.entities) if perception.entities else 'none'}
- Tool hint: {perception.tool_hint or 'none'}
- Time references: {', '.join(perception.time_refs) if perception.time_refs else 'none'}

RELEVANT MEMORY:
{memory_text}

PREVIOUS STEPS IN THIS CONVERSATION:
{iteration_context or "This is the first step."}

DECISION FLOW:

1. UNDERSTAND the user's intent:
   - READ EMAIL: "check emails", "unread", "inbox", "summarize emails"
   - SEARCH EMAIL: "emails from", "emails about", "find email"
   - THREAD / CONVERSATION: "conversation with", "thread with", "summarize thread"
   - ATTACHMENT / DOCUMENT: "document", "attachment", "file sent", "pdf", "summarize the file"
   - DOCUMENT QUERY: "what does the document say about", "find in document", "search in the pdf"
   - WRITE EMAIL: "send email", "write email", "email someone", "tell them", "message"
   - READ CALENDAR: "schedule", "meetings", "events", "busy", "free", "available", "what's on"
   - WRITE CALENDAR: "schedule a meeting", "add event", "create", "book", "set up"
   - UNRELATED: anything else

2. PICK the right tool:

   READ EMAIL (today / unread):
   → Call get_unread_emails_today (no params)

   READ EMAIL (specific time period):
   → Call get_emails_by_date_range|YYYY-MM-DD|YYYY-MM-DD

   SEARCH EMAIL (by person, topic, or keyword):
   → Call search_emails|gmail_query

   SUMMARISE A THREAD / CONVERSATION:
   Step 1 → Call search_emails to find emails matching the person/topic. Results include a threadId field.
   Step 2 → Pick the most relevant threadId from the results and call get_email_thread|<threadId>
   Step 3 → FINAL_ANSWER summarising the conversation.

   READ ATTACHMENT / DOCUMENT:
   Step 1 → Call search_emails with "has:attachment" plus the person/topic
   Step 2 → Pick the most relevant messageId and call get_email_attachments|<messageId>
            (This automatically indexes the full document into the search index for RAG)
   Step 3 → For a general summary, give FINAL_ANSWER based on the preview text.
            For specific questions, call search_indexed_documents|<specific query about the document>
   Step 4 → FINAL_ANSWER with the information from the retrieved chunks.

   DOCUMENT QUERY (follow-up about an already-indexed document):
   → Call search_indexed_documents|<query>
   → FINAL_ANSWER based on the retrieved chunks.

   WRITE EMAIL:
   → Call send_email|to_address|subject|body
   → The body should be professional and well-written

   READ CALENDAR (today):
   → Call get_todays_events (no params)

   READ CALENDAR (specific date):
   → Call get_events_for_date|YYYY-MM-DD

   READ CALENDAR (free/busy check):
   → Call check_free_slots|YYYY-MM-DD

   WRITE CALENDAR:
   → Call create_event|title|YYYY-MM-DD|HH:MM|HH:MM|attendee_emails
   → If no attendees, leave last param empty
   → If no end time given, assume 1 hour duration

   UNRELATED:
   → Give a FINAL_ANSWER directly

3. After receiving tool results, give a FINAL_ANSWER with a clear, friendly summary.
   Do NOT call another tool unless absolutely necessary for multi-step flows.

DATE PARSING (today is {today_str}):
- Convert all natural dates to YYYY-MM-DD format
- "5th Feb" or "Feb 5th" or "February 5" → 2026-02-05
- "tomorrow" → calculate from {today_str}
- "next Friday" → calculate from {today_str}
- Time must be HH:MM in 24-hour format (e.g. 14:00 for 2 PM)

EXAMPLES:
- FUNCTION_CALL: get_unread_emails_today
- FUNCTION_CALL: get_emails_by_date_range|2026-02-01|2026-02-07
- FUNCTION_CALL: search_emails|from:dhruv
- FUNCTION_CALL: search_emails|from:sarah OR to:sarah
- FUNCTION_CALL: get_email_thread|18d1a2b3c4e5f678
- FUNCTION_CALL: search_emails|from:dhruv has:attachment
- FUNCTION_CALL: get_email_attachments|18d1a2b3c4e5f678
- FUNCTION_CALL: search_indexed_documents|revenue figures Q3
- FUNCTION_CALL: send_email|john@example.com|Meeting follow-up|Hi John, just following up.
- FUNCTION_CALL: get_todays_events
- FUNCTION_CALL: get_events_for_date|2026-03-05
- FUNCTION_CALL: check_free_slots|2026-02-10
- FUNCTION_CALL: create_event|Dentist appointment|2026-03-05|14:00|15:00|
- FUNCTION_CALL: create_event|Team sync|2026-03-05|10:00|11:00|john@co.com,sara@co.com
- FINAL_ANSWER: [You have 3 meetings today. The first one is a standup at 9 AM.]

DO NOT include any explanations or additional text.
Your entire response should be a single line starting with either FUNCTION_CALL: or FINAL_ANSWER:"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=system_prompt,
        )
        raw = response.text.strip()
        log.info("Decision LLM output: %s", raw)

        # Find the FUNCTION_CALL or FINAL_ANSWER line
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("FUNCTION_CALL:") or line.startswith("FINAL_ANSWER:"):
                return line

        return raw.strip()

    except Exception as e:
        log.error("Decision generation failed: %s", e)
        return "FINAL_ANSWER: [Sorry, I couldn't process your request. Please try again.]"
