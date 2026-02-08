"""
Google Calendar API client — read and write access to the user's calendar.
Assumes token.json (with calendar scopes) already exists one level up.
"""

import os
import datetime
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger("email-assistant.calendar")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "token.json")

# User's local timezone — used for all Calendar API calls
TIMEZONE = "America/Winnipeg"  # CST / Central Time
CST = datetime.timezone(datetime.timedelta(hours=-6))


def get_calendar_service():
    """Return an authorised Google Calendar API service instance."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"token.json not found at {os.path.abspath(TOKEN_PATH)}. "
            "Please complete the OAuth flow first."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build("calendar", "v3", credentials=creds)
    return service


def get_todays_events() -> list[dict]:
    """
    Fetch all events happening today from the user's primary calendar.

    Returns a list of dicts:
        [{"summary": "...", "start": "...", "end": "...", "attendees": [...]}, ...]
    """
    service = get_calendar_service()

    now = datetime.datetime.now(CST)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    log.info("Fetching events from %s to %s (%s)", start_of_day, end_of_day, TIMEZONE)

    results = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        timeZone=TIMEZONE,
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,
    ).execute()

    raw_events = results.get("items", [])
    log.info("Found %d events today", len(raw_events))

    events: list[dict] = []
    for event in raw_events:
        start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
        end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date", ""))
        attendees = [
            a.get("email", "unknown")
            for a in event.get("attendees", [])
        ]

        events.append({
            "summary": event.get("summary", "(no title)"),
            "start": start,
            "end": end,
            "attendees": attendees,
            "location": event.get("location", ""),
            "description": event.get("description", ""),
        })

    return events


def get_events_for_date(date: str) -> list[dict]:
    """
    Fetch all events on a specific date.

    Args:
        date: Date string in YYYY-MM-DD format (e.g. "2026-03-05")

    Returns the same format as get_todays_events().
    """
    service = get_calendar_service()

    target = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=CST)
    start_of_day = target.replace(hour=0, minute=0, second=0).isoformat()
    end_of_day = target.replace(hour=23, minute=59, second=59).isoformat()

    log.info("Fetching events for %s (%s)", date, TIMEZONE)

    results = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        timeZone=TIMEZONE,
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,
    ).execute()

    raw_events = results.get("items", [])
    log.info("Found %d events for %s", len(raw_events), date)

    events: list[dict] = []
    for event in raw_events:
        start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
        end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date", ""))
        attendees = [
            a.get("email", "unknown")
            for a in event.get("attendees", [])
        ]

        events.append({
            "summary": event.get("summary", "(no title)"),
            "start": start,
            "end": end,
            "attendees": attendees,
            "location": event.get("location", ""),
            "description": event.get("description", ""),
        })

    return events


def check_free_slots(date: str) -> dict:
    """
    Check free/busy time blocks for a given date (8 AM – 6 PM).
    Works by fetching events for the day and computing gaps.

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        {"date": "...", "busy": [...], "free": [...]}
    """
    log.info("Checking free/busy for %s (8AM-6PM)", date)

    events = get_events_for_date(date)

    day_start = datetime.datetime.strptime(f"{date} 08:00", "%Y-%m-%d %H:%M")
    day_end = datetime.datetime.strptime(f"{date} 18:00", "%Y-%m-%d %H:%M")

    # Parse event start/end times into datetime objects
    busy_blocks = []
    for ev in events:
        try:
            # Events come back as ISO strings like "2026-02-12T09:00:00-06:00"
            raw_start = ev.get("start", "")
            raw_end = ev.get("end", "")
            if not raw_start or not raw_end:
                continue

            ev_start = datetime.datetime.fromisoformat(raw_start)
            ev_end = datetime.datetime.fromisoformat(raw_end)

            # Strip timezone info for simple comparison
            ev_start = ev_start.replace(tzinfo=None)
            ev_end = ev_end.replace(tzinfo=None)

            # Clamp to working hours
            ev_start = max(ev_start, day_start)
            ev_end = min(ev_end, day_end)

            if ev_start < ev_end:
                busy_blocks.append((ev_start, ev_end, ev.get("summary", "")))
        except (ValueError, TypeError):
            continue

    # Sort by start time
    busy_blocks.sort(key=lambda b: b[0])

    # Calculate free slots between busy blocks
    free_slots = []
    current = day_start

    for start, end, _ in busy_blocks:
        if current < start:
            free_slots.append({
                "start": current.strftime("%I:%M %p"),
                "end": start.strftime("%I:%M %p"),
            })
        current = max(current, end)

    if current < day_end:
        free_slots.append({
            "start": current.strftime("%I:%M %p"),
            "end": day_end.strftime("%I:%M %p"),
        })

    busy_formatted = [
        {
            "start": s.strftime("%I:%M %p"),
            "end": e.strftime("%I:%M %p"),
            "event": title,
        }
        for s, e, title in busy_blocks
    ]

    log.info("Found %d busy blocks, %d free slots", len(busy_formatted), len(free_slots))

    return {
        "date": date,
        "busy": busy_formatted,
        "free": free_slots,
    }


def create_event(title: str, date: str, start_time: str, end_time: str, attendees: str = "") -> dict:
    """
    Create a new calendar event, optionally with attendees.

    Args:
        title: Event title (e.g. "Dentist appointment")
        date: Date in YYYY-MM-DD format (e.g. "2026-03-05")
        start_time: Start time in HH:MM format, 24h (e.g. "14:00")
        end_time: End time in HH:MM format, 24h (e.g. "15:00")
        attendees: Comma-separated email addresses (e.g. "a@co.com,b@co.com") or empty string

    Returns:
        {"status": "created", "summary": "...", "start": "...", "end": "...", "link": "...", "attendees": [...]}
    """
    service = get_calendar_service()

    start_dt = datetime.datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")

    log.info("Creating event: '%s' on %s from %s to %s", title, date, start_time, end_time)

    event_body = {
        "summary": title,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    # Add attendees if provided — Google Calendar sends invite emails automatically
    attendee_list = []
    if attendees and attendees.strip():
        attendee_list = [email.strip() for email in attendees.split(",") if email.strip()]
        event_body["attendees"] = [{"email": e} for e in attendee_list]

    created = service.events().insert(
        calendarId="primary",
        body=event_body,
        sendUpdates="all",  # sends invite emails to attendees
    ).execute()

    log.info("Event created: %s (attendees: %s)", created.get("htmlLink"), attendee_list)

    return {
        "status": "created",
        "summary": created.get("summary", title),
        "start": start_time,
        "end": end_time,
        "date": date,
        "link": created.get("htmlLink", ""),
        "attendees": attendee_list,
    }
