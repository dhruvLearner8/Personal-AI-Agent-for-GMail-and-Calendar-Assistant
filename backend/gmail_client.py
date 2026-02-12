"""
Gmail API client — read and send access to the user's inbox.
Assumes token.json already exists in the project root (one level up from /backend).
"""

import os
import datetime
import logging
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger("email-assistant.gmail")

# Read-only scope — the only permission this app needs
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# token.json lives in the project root (one level up from /backend)
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "token.json")


def get_gmail_service():
    """Return an authorised Gmail API service instance."""
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"token.json not found at {os.path.abspath(TOKEN_PATH)}. "
            "Please complete the OAuth flow first."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build("gmail", "v1", credentials=creds)
    return service


def get_unread_emails_today() -> list[dict]:
    """
    Fetch unread emails received today from the user's Gmail inbox.

    Returns a list of dicts:
        [{"from": "...", "subject": "...", "snippet": "..."}, ...]
    """
    service = get_gmail_service()

    # Gmail search query: unread + received today
    today = datetime.date.today().strftime("%Y/%m/%d")
    query = f"is:unread after:{today}"
    log.info("Gmail query: %s", query)

    results = service.users().messages().list(
        userId="me", q=query, maxResults=25
    ).execute()

    messages = results.get("messages", [])
    log.info("Found %d raw message IDs", len(messages))

    if not messages:
        return []

    emails: list[dict] = []
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_meta["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"],
            )
            .execute()
        )

        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        emails.append({
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
        })

    log.info("Returning %d parsed emails", len(emails))
    return emails


def get_emails_by_date_range(start_date: str, end_date: str) -> list[dict]:
    """
    Fetch emails within a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format (inclusive)
        end_date: End date in YYYY-MM-DD format (inclusive)

    Returns a list of dicts:
        [{"from": "...", "subject": "...", "snippet": "...", "date": "..."}, ...]
    """
    service = get_gmail_service()

    # Gmail uses YYYY/MM/DD format for date queries
    start = start_date.replace("-", "/")
    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
    end = end_dt.strftime("%Y/%m/%d")

    query = f"after:{start} before:{end}"
    log.info("Gmail query: %s", query)

    results = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()

    messages = results.get("messages", [])
    log.info("Found %d raw message IDs", len(messages))

    if not messages:
        return []

    emails: list[dict] = []
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_meta["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )

        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        emails.append({
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
            "date": headers.get("Date", ""),
        })

    log.info("Returning %d parsed emails for %s to %s", len(emails), start_date, end_date)
    return emails


def search_emails(query: str) -> list[dict]:
    """
    Search emails using Gmail search syntax.

    Args:
        query: Gmail search query (e.g. "from:dhruv", "subject:meeting", "from:john after:2026/02/01")

    Returns a list of dicts:
        [{"from": "...", "subject": "...", "snippet": "...", "date": "..."}, ...]
    """
    service = get_gmail_service()

    log.info("Gmail search query: %s", query)

    results = service.users().messages().list(
        userId="me", q=query, maxResults=25
    ).execute()

    messages = results.get("messages", [])
    log.info("Found %d results for query: %s", len(messages), query)

    if not messages:
        return []

    emails: list[dict] = []
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_meta["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )

        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }
        emails.append({
            "messageId": msg.get("id", ""),
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
            "date": headers.get("Date", ""),
            "threadId": msg.get("threadId", ""),
        })

    log.info("Returning %d parsed results", len(emails))
    return emails


# ── Thread helpers ──────────────────────────────────────────────────


def _extract_body_text(payload: dict) -> str:
    """
    Recursively walk a Gmail message payload and return the plain-text body.
    Falls back to snippet if nothing usable is found.
    """
    # Simple (non-multipart) message
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart — recurse into parts
    for part in payload.get("parts", []):
        text = _extract_body_text(part)
        if text:
            return text

    # Last resort: decode body.data even if mimeType isn't text/plain
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return ""


def get_email_thread(thread_id: str) -> dict:
    """
    Fetch every message in a Gmail thread and return them chronologically
    with full body text so the LLM can summarise the conversation.

    Returns:
        {
            "thread_id": "...",
            "subject": "Re: ...",
            "message_count": 10,
            "messages": [
                {"from": "...", "to": "...", "date": "...", "body": "..."},
                ...
            ]
        }
    """
    service = get_gmail_service()

    log.info("Fetching thread %s", thread_id)
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="full"
    ).execute()

    raw_messages = thread.get("messages", [])
    log.info("Thread %s contains %d messages", thread_id, len(raw_messages))

    subject = ""
    messages: list[dict] = []

    for msg in raw_messages:
        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        if not subject:
            subject = headers.get("Subject", "(no subject)")

        body = _extract_body_text(msg.get("payload", {}))
        # Trim extremely long bodies to keep prompt size manageable
        if len(body) > 2000:
            body = body[:2000] + "\n... [trimmed]"

        messages.append({
            "from": headers.get("From", "Unknown"),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "body": body.strip() or msg.get("snippet", ""),
        })

    return {
        "thread_id": thread_id,
        "subject": subject,
        "message_count": len(messages),
        "messages": messages,
    }


# ── Attachment helpers ──────────────────────────────────────────────


def _extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using PyPDF2."""
    try:
        import io
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        log.warning("PDF extraction failed: %s", e)
        return f"[Could not extract PDF text: {e}]"


def _extract_text_from_docx(data: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import io
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except Exception as e:
        log.warning("DOCX extraction failed: %s", e)
        return f"[Could not extract DOCX text: {e}]"


def _extract_attachment_text(filename: str, data: bytes) -> str:
    """
    Try to extract readable text from an attachment based on its file extension.
    Returns the text content or a descriptive fallback.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_text_from_pdf(data)
    elif lower.endswith(".docx"):
        return _extract_text_from_docx(data)
    elif lower.endswith((".txt", ".csv", ".md", ".json", ".xml", ".html", ".log")):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return "[Could not decode text file]"
    else:
        return f"[Binary file — cannot extract text from {filename}]"


def get_email_attachments(message_id: str) -> dict:
    """
    Fetch attachments from a specific email and extract their text content.

    Args:
        message_id: The Gmail message ID (returned by search_emails in each result's 'messageId' field)

    Returns:
        {
            "message_id": "...",
            "subject": "...",
            "from": "...",
            "attachment_count": 2,
            "attachments": [
                {"filename": "report.pdf", "mime_type": "application/pdf", "size": 12345, "content": "extracted text..."},
                ...
            ]
        }
    """
    service = get_gmail_service()

    log.info("Fetching attachments for message %s", message_id)

    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {
        h["name"]: h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }
    subject = headers.get("Subject", "(no subject)")
    sender = headers.get("From", "Unknown")

    # Walk parts to find attachments
    attachments: list[dict] = []

    def _walk_parts(parts):
        for part in parts:
            filename = part.get("filename", "")
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")

            if filename and attachment_id:
                # Download the actual attachment data
                log.info("Downloading attachment: %s (%s)", filename, mime_type)
                att = service.users().messages().attachments().get(
                    userId="me", messageId=message_id, id=attachment_id
                ).execute()

                raw_data = base64.urlsafe_b64decode(att.get("data", ""))
                size = len(raw_data)

                # Extract text content (full — no trimming here, MCP layer handles it)
                content = _extract_attachment_text(filename, raw_data)

                attachments.append({
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": size,
                    "content": content,
                })

            # Recurse into nested multipart
            if part.get("parts"):
                _walk_parts(part["parts"])

    payload = msg.get("payload", {})
    if payload.get("parts"):
        _walk_parts(payload["parts"])

    log.info("Found %d attachments in message %s", len(attachments), message_id)

    return {
        "message_id": message_id,
        "subject": subject,
        "from": sender,
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain-text email body

    Returns:
        {"status": "sent", "to": "...", "subject": "...", "message_id": "..."}
    """
    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    log.info("Sending email to %s — subject: %s", to, subject)

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    log.info("Email sent, message ID: %s", result.get("id"))

    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "message_id": result.get("id", ""),
    }
