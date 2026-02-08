"""
FastAPI HTTP server — thin REST layer that the React frontend calls.
Wraps the same functions used by the MCP tools so the logic is shared.

Run:
    cd backend
    uvicorn server:app --reload --port 8000
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gmail_client import get_unread_emails_today
from agent import handle_chat

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("email-assistant")

# ── FastAPI app ───────────────────────────────────────────────────────
app = FastAPI(
    title="AI Email Assistant API",
    version="0.1.0",
    description="Backend for the AI Email Assistant — agent-ready.",
)

# Allow the Vite dev server (localhost:5173) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────
class UnreadResponse(BaseModel):
    emails: list[dict]
    error: str | None = None


class ChatRequest(BaseModel):
    message: str

# ── Routes ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "service": "AI Email Assistant API"}


@app.get("/emails/unread-today", response_model=UnreadResponse)
async def unread_today():
    """Fetch today's unread emails from Gmail."""
    log.info("-> Fetching unread emails for today ...")
    try:
        emails = get_unread_emails_today()
        log.info("   Found %d unread emails", len(emails))
        return UnreadResponse(emails=emails)
    except FileNotFoundError as e:
        log.warning("   token.json missing: %s", e)
        return UnreadResponse(emails=[], error=str(e))
    except Exception as e:
        log.error("   Gmail API error: %s", e)
        return UnreadResponse(emails=[], error=f"Gmail error: {str(e)}")


@app.post("/chat")
async def chat(body: ChatRequest):
    """Send a message to the agent, receive reply + optional structured context."""
    log.info("-> Chat: %s", body.message)
    result = await handle_chat(body.message)
    log.info("   Reply: %s", result.get("reply", "")[:80])
    return {
        "reply": result.get("reply", ""),
        "context": result.get("context", None),
    }