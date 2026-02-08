"""
MCP tool definitions for the AI Email & Calendar Assistant.

These tools are consumed by the agent (via stdio) and wrap the
gmail_client / calendar_client functions.

Run standalone:
    python mcp_tools.py        # stdio transport (for MCP clients)
    python mcp_tools.py dev    # dev/inspector mode
"""

import sys
from mcp.server.fastmcp import FastMCP
from gmail_client import get_unread_emails_today as _fetch_unread
from gmail_client import get_emails_by_date_range as _fetch_emails_by_range
from gmail_client import search_emails as _search_emails
from gmail_client import get_email_thread as _get_email_thread
from gmail_client import get_email_attachments as _get_email_attachments
from gmail_client import send_email as _send_email
from calendar_client import (
    get_todays_events as _get_todays_events,
    get_events_for_date as _get_events_for_date,
    check_free_slots as _check_free_slots,
    create_event as _create_event,
)

# ── MCP server instance ──────────────────────────────────────────────
mcp = FastMCP("EmailCalendarAssistant")


@mcp.tool()
def get_unread_emails_today() -> dict:
    """
    Returns unread emails from today.

    Output format:
    {
      "emails": [
        {"from": "name@email.com", "subject": "Meeting update", "snippet": "Quick update about..."}
      ]
    }
    """
    print("CALLED: get_unread_emails_today()")
    try:
        emails = _fetch_unread()
        return {"emails": emails}
    except FileNotFoundError as e:
        return {"error": str(e), "emails": []}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "emails": []}


@mcp.tool()
def get_emails_by_date_range(start_date: str, end_date: str) -> dict:
    """
    Fetch emails within a specific date range.

    Args:
        start_date: Start date in YYYY-MM-DD format (e.g. "2026-02-01")
        end_date: End date in YYYY-MM-DD format (e.g. "2026-02-07")

    Output format:
    {
      "emails": [
        {"from": "name@email.com", "subject": "...", "snippet": "...", "date": "..."}
      ],
      "start_date": "2026-02-01",
      "end_date": "2026-02-07"
    }
    """
    print(f"CALLED: get_emails_by_date_range(start={start_date}, end={end_date})")
    try:
        emails = _fetch_emails_by_range(start_date, end_date)
        return {"emails": emails, "start_date": start_date, "end_date": end_date}
    except FileNotFoundError as e:
        return {"error": str(e), "emails": []}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "emails": []}


@mcp.tool()
def search_emails(query: str) -> dict:
    """
    Search emails using Gmail search syntax. Use this to find emails from a specific person,
    about a specific topic, or matching any Gmail search query.

    Args:
        query: Gmail search query. Examples:
            - "from:dhruv" — emails from dhruv
            - "to:sarah" — emails sent to sarah
            - "from:john subject:meeting" — emails from john about meetings
            - "from:boss@company.com after:2026/02/01" — emails from boss since Feb 1
            - "subject:invoice" — emails with invoice in subject

    Output format:
    {
      "emails": [
        {"from": "...", "subject": "...", "snippet": "...", "date": "..."}
      ],
      "query": "from:dhruv"
    }
    """
    print(f"CALLED: search_emails(query={query})")
    try:
        emails = _search_emails(query)
        return {"emails": emails, "query": query}
    except FileNotFoundError as e:
        return {"error": str(e), "emails": []}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "emails": []}


@mcp.tool()
def get_email_thread(thread_id: str) -> dict:
    """
    Fetch every message in a Gmail thread with full body text.
    Use this after search_emails to drill into a specific conversation.

    Args:
        thread_id: The Gmail thread ID (returned by search_emails in each result's 'threadId' field)

    Output format:
    {
      "thread_id": "...",
      "subject": "Re: Project update",
      "message_count": 10,
      "messages": [
        {"from": "...", "to": "...", "date": "...", "body": "full email text..."}
      ]
    }
    """
    print(f"CALLED: get_email_thread(thread_id={thread_id})")
    try:
        result = _get_email_thread(thread_id)
        return result
    except FileNotFoundError as e:
        return {"error": str(e), "messages": []}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "messages": []}


@mcp.tool()
def get_email_attachments(message_id: str) -> dict:
    """
    Fetch attachments from a specific email and extract their text content.
    Use this after search_emails (with has:attachment) to read documents sent in an email.

    Args:
        message_id: The Gmail message ID (returned by search_emails in each result's 'messageId' field)

    Output format:
    {
      "message_id": "...",
      "subject": "...",
      "from": "...",
      "attachment_count": 2,
      "attachments": [
        {"filename": "report.pdf", "mime_type": "application/pdf", "size": 12345, "content": "extracted text..."}
      ]
    }
    """
    print(f"CALLED: get_email_attachments(message_id={message_id})")
    try:
        result = _get_email_attachments(message_id)
        return result
    except FileNotFoundError as e:
        return {"error": str(e), "attachments": []}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "attachments": []}


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail on behalf of the user.

    Args:
        to: Recipient email address (e.g. "john@example.com")
        subject: Email subject line (e.g. "Meeting follow-up")
        body: Plain-text email body content

    Output format:
    {
      "status": "sent",
      "to": "john@example.com",
      "subject": "Meeting follow-up",
      "message_id": "..."
    }
    """
    print(f"CALLED: send_email(to={to}, subject={subject})")
    try:
        result = _send_email(to, subject, body)
        return result
    except FileNotFoundError as e:
        return {"error": str(e), "status": "failed"}
    except Exception as e:
        return {"error": f"Gmail API error: {str(e)}", "status": "failed"}


# ── Calendar tools ────────────────────────────────────────────────────

@mcp.tool()
def get_todays_events() -> dict:
    """
    Returns all events from today's calendar.

    Output format:
    {
      "events": [
        {"summary": "Team standup", "start": "09:00", "end": "09:30", "attendees": [...], "location": "", "description": ""}
      ]
    }
    """
    print("CALLED: get_todays_events()")
    try:
        events = _get_todays_events()
        return {"events": events}
    except FileNotFoundError as e:
        return {"error": str(e), "events": []}
    except Exception as e:
        return {"error": f"Calendar API error: {str(e)}", "events": []}


@mcp.tool()
def get_events_for_date(date: str) -> dict:
    """
    Returns all events on a specific date.

    Args:
        date: Date in YYYY-MM-DD format (e.g. "2026-03-05")

    Output format: same as get_todays_events.
    """
    print(f"CALLED: get_events_for_date(date={date})")
    try:
        events = _get_events_for_date(date)
        return {"events": events}
    except FileNotFoundError as e:
        return {"error": str(e), "events": []}
    except Exception as e:
        return {"error": f"Calendar API error: {str(e)}", "events": []}


@mcp.tool()
def check_free_slots(date: str) -> dict:
    """
    Check free and busy time slots for a given date (8 AM to 6 PM).

    Args:
        date: Date in YYYY-MM-DD format (e.g. "2026-03-05")

    Output format:
    {
      "date": "2026-03-05",
      "busy": [{"start": "09:00 AM", "end": "10:00 AM"}],
      "free": [{"start": "08:00 AM", "end": "09:00 AM"}, ...]
    }
    """
    print(f"CALLED: check_free_slots(date={date})")
    try:
        result = _check_free_slots(date)
        return result
    except FileNotFoundError as e:
        return {"error": str(e), "date": date, "busy": [], "free": []}
    except Exception as e:
        return {"error": f"Calendar API error: {str(e)}", "date": date, "busy": [], "free": []}


@mcp.tool()
def create_event(title: str, date: str, start_time: str, end_time: str, attendees: str = "") -> dict:
    """
    Create a new event on the user's Google Calendar.
    If attendees are provided, Google Calendar automatically sends them invite emails.

    Args:
        title: Event title (e.g. "Dentist appointment")
        date: Date in YYYY-MM-DD format (e.g. "2026-03-05")
        start_time: Start time in HH:MM 24-hour format (e.g. "14:00")
        end_time: End time in HH:MM 24-hour format (e.g. "15:00")
        attendees: Comma-separated email addresses (e.g. "john@co.com,sara@co.com") or empty string for no attendees

    Output format:
    {
      "status": "created",
      "summary": "Dentist appointment",
      "date": "2026-03-05",
      "start": "14:00",
      "end": "15:00",
      "link": "https://calendar.google.com/...",
      "attendees": ["john@co.com", "sara@co.com"]
    }
    """
    print(f"CALLED: create_event(title={title}, date={date}, start={start_time}, end={end_time}, attendees={attendees})")
    try:
        result = _create_event(title, date, start_time, end_time, attendees)
        return result
    except FileNotFoundError as e:
        return {"error": str(e), "status": "failed"}
    except Exception as e:
        return {"error": f"Calendar API error: {str(e)}", "status": "failed"}


# ── Entry-point (for running as standalone MCP server) ────────────────
if __name__ == "__main__":
    print("Starting Email Assistant MCP server ...")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()
    else:
        mcp.run(transport="stdio")
