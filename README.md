# Demo
https://drive.google.com/file/d/1f6T-BQvqr8CsJ6vMoArBD12LBl1k59Fm/view?usp=sharing

# AI Email & Calendar Assistant

A full-stack AI assistant that manages your Gmail inbox and Google Calendar through natural language. Powered by **Google Gemini 2.0 Flash**, it uses an agentic architecture with the **Model Context Protocol (MCP)** to orchestrate multi-step workflows — reading emails, summarizing threads, extracting document attachments, managing calendar events, and sending emails — all from a single chat interface.

> **This is not a ChatGPT wrapper.** The LLM autonomously decides which tools to call, chains them across multiple iterations, and synthesizes results into human-friendly responses.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [File Reference](#file-reference)
- [Use Cases & Examples](#use-cases--examples)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [How the Agent Works](#how-the-agent-works)
- [Future Improvements](#future-improvements)

---

## Features

### Email
| Feature | Description |
|---|---|
| **Read Unread Emails** | Fetch and summarize today's unread inbox |
| **Search Emails** | Gmail-syntax search (by sender, subject, date, keyword) |
| **Thread Summarization** | Fetch an entire email thread and summarize the conversation |
| **Attachment Extraction** | Download PDF/DOCX/text attachments and extract readable content |
| **Send Emails** | Compose and send emails with context-aware drafting |
| **Date Range Queries** | "Show me emails from last week" |

### Calendar
| Feature | Description |
|---|---|
| **View Today's Schedule** | List all events for today |
| **View Any Date** | "What's on my calendar March 5th?" |
| **Free/Busy Check** | Visual timeline of availability (8 AM – 6 PM) |
| **Create Events** | Schedule meetings with title, time, and attendees |
| **Auto Invites** | Attendees receive Google Calendar invitations automatically |

### AI & Agent
| Feature | Description |
|---|---|
| **Natural Language Input** | No commands to memorize — just chat |
| **Multi-Step Reasoning** | Agent chains 2-3 tool calls to answer complex queries |
| **Date Understanding** | Parses "next Friday", "Feb 5th", "tomorrow" into dates |
| **Context Panel** | Structured side panel shows emails, events, timelines alongside chat |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Chat Window  │  │  Chat Input  │  │ Context Panel  │ │
│  │  (messages)  │  │  (user msg)  │  │ (emails/events)│ │
│  └──────┬───────┘  └──────┬───────┘  └───────▲────────┘ │
│         │                 │                   │          │
└─────────┼─────────────────┼───────────────────┼──────────┘
          │          POST /chat                 │
          ▼                 ▼                   │
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Server (server.py)               │
│                         │                                │
│                         ▼                                │
│              ┌─────────────────────┐                     │
│              │   Agent (agent.py)  │                     │
│              │                     │                     │
│              │  ┌───────────────┐  │                     │
│              │  │ Gemini 2.0    │  │                     │
│              │  │ Flash LLM     │  │                     │
│              │  └───────┬───────┘  │                     │
│              │          │          │                     │
│              │   FUNCTION_CALL /   │                     │
│              │   FINAL_ANSWER      │                     │
│              └──────────┼──────────┘                     │
│                         │ stdio                          │
│                         ▼                                │
│              ┌─────────────────────┐                     │
│              │  MCP Server         │                     │
│              │  (mcp_tools.py)     │                     │
│              │                     │                     │
│              │  10 tools exposed   │                     │
│              └──────────┬──────────┘                     │
│                         │                                │
└─────────────────────────┼────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
   ┌──────────────────┐    ┌──────────────────┐
   │  gmail_client.py │    │calendar_client.py│
   │                  │    │                  │
   │  Gmail API       │    │  Calendar API    │
   │  - Read/Search   │    │  - Read Events   │
   │  - Threads       │    │  - Free Slots    │
   │  - Attachments   │    │  - Create Events │
   │  - Send          │    │                  │
   └──────────────────┘    └──────────────────┘
              │                       │
              ▼                       ▼
        ┌──────────────────────────────────┐
        │       Google APIs (OAuth 2.0)    │
        │   Gmail API  ·  Calendar API     │
        └──────────────────────────────────┘
```

### Data Flow

1. User types a message in the **React frontend**
2. Frontend sends `POST /chat` to the **FastAPI server**
3. Server calls `handle_chat()` in the **Agent**
4. Agent sends the message + system prompt to **Gemini 2.0 Flash**
5. Gemini responds with either:
   - `FUNCTION_CALL: tool_name|param1|param2` → Agent calls the MCP tool, appends result, loops back to step 4
   - `FINAL_ANSWER: response text` → Agent returns the response
6. Agent returns `{reply, context}` — the text response + structured data for the side panel
7. Frontend renders the chat reply and displays context (emails, events, etc.) in the side panel

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 6 |
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **AI Model** | Google Gemini 2.0 Flash |
| **Tool Protocol** | Model Context Protocol (MCP) via FastMCP |
| **Google APIs** | Gmail API, Google Calendar API |
| **Auth** | OAuth 2.0 (offline access) |
| **Doc Parsing** | PyPDF2 (PDF), python-docx (DOCX) |
| **Package Manager** | uv (backend), npm (frontend) |

---

## Project Structure

```
Session-5/
├── README.md
├── .gitignore
│
├── backend/
│   ├── pyproject.toml          # Python dependencies (managed by uv)
│   ├── .python-version         # Python 3.12
│   ├── server.py               # FastAPI HTTP server
│   ├── agent.py                # LLM agent with tool orchestration loop
│   ├── mcp_tools.py            # MCP server — exposes 10 tools
│   ├── gmail_client.py         # Gmail API client functions
│   ├── calendar_client.py      # Google Calendar API client functions
│   └── generate_token.py       # One-time OAuth token generation script
│
└── frontend/
    ├── package.json
    ├── vite.config.js          # Dev server + API proxy config
    ├── index.html
    └── src/
        ├── main.jsx            # React entry point
        ├── App.jsx             # Main app — layout, state, routing
        ├── api.js              # API client (fetch calls to backend)
        ├── index.css           # All styles
        └── components/
            ├── ChatWindow.jsx      # Scrollable message list
            ├── ChatInput.jsx       # Text input + send button
            ├── QuickActions.jsx    # Quick action buttons
            ├── ContextPanel.jsx    # Dynamic side panel renderer
            ├── EmailCard.jsx       # Email display card
            ├── EventCard.jsx       # Calendar event card
            └── FreeSlotTimeline.jsx # Visual availability timeline
```

---

## File Reference

### Backend

| File | Responsibility | Key Functions |
|---|---|---|
| `server.py` | HTTP layer — receives requests from frontend, routes to agent | `GET /`, `GET /emails/unread-today`, `POST /chat` |
| `agent.py` | Brain — sends user message to Gemini, parses tool calls, loops until final answer | `handle_chat()`, `_build_context()`, `generate_with_timeout()` |
| `mcp_tools.py` | Tool layer — wraps Gmail/Calendar functions as MCP tools (stdio transport) | 10 `@mcp.tool()` functions |
| `gmail_client.py` | Gmail API — all direct interactions with Gmail | `get_unread_emails_today()`, `search_emails()`, `get_email_thread()`, `get_email_attachments()`, `send_email()`, `get_emails_by_date_range()` |
| `calendar_client.py` | Calendar API — all direct interactions with Google Calendar | `get_todays_events()`, `get_events_for_date()`, `check_free_slots()`, `create_event()` |
| `generate_token.py` | One-time script to run Google OAuth and save `token.json` | Run once during setup |

### Frontend

| File | Responsibility |
|---|---|
| `App.jsx` | Main layout — manages messages state, calls API, renders two-column layout |
| `ChatWindow.jsx` | Displays chat messages with auto-scroll and typing indicator |
| `ChatInput.jsx` | User input field with send button |
| `QuickActions.jsx` | Quick-action buttons (e.g., "Summarize unread emails") |
| `ContextPanel.jsx` | Renders structured data in the side panel based on context type (emails, events, threads, attachments, free slots) |
| `EmailCard.jsx` | Individual email card (avatar, sender, subject, snippet) |
| `EventCard.jsx` | Calendar event card (time, title, location, attendees) |
| `FreeSlotTimeline.jsx` | Visual busy/free timeline bar |
| `api.js` | API client — `fetchUnreadToday()`, `sendChatMessage()` |

---

## Use Cases & Examples

### Email Management

| You say | What the agent does |
|---|---|
| "Summarize my unread emails" | Calls `get_unread_emails_today` → summarizes in chat, shows email cards in panel |
| "Show me emails from last week" | Calculates date range → calls `get_emails_by_date_range` |
| "Find emails from dhruv about the project" | Calls `search_emails\|from:dhruv subject:project` |
| "Summarize the thread with Sarah" | `search_emails` → picks latest thread → `get_email_thread` → summarizes full conversation |
| "What's in the PDF dhruv sent me?" | `search_emails\|from:dhruv has:attachment` → `get_email_attachments` → extracts PDF text → summarizes |
| "Send an email to john@example.com saying I'll be late" | Crafts a polite email → calls `send_email` |

### Calendar Management

| You say | What the agent does |
|---|---|
| "What's on my schedule today?" | Calls `get_todays_events` → shows event cards in panel |
| "Do I have meetings on Feb 12th?" | Calls `get_events_for_date\|2026-02-12` |
| "Am I free Thursday afternoon?" | Calls `check_free_slots` → shows visual timeline |
| "Schedule a dentist appointment on March 5th from 2 to 3 PM" | Calls `create_event` → shows confirmation card with Google Calendar link |
| "Set up a meeting with sarah@co.com tomorrow at 10" | Creates event with attendee → Google sends invite automatically |

### Multi-Step (Agentic)

| You say | Agent steps |
|---|---|
| "Summarize the document sent by dhruv" | 1. Search emails with attachment → 2. Download & extract PDF → 3. Summarize content |
| "What did sarah and I discuss last week?" | 1. Search emails from/to sarah → 2. Fetch thread → 3. Summarize conversation |

---

## Setup & Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **uv** (Python package manager) — [install guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud Project** with Gmail API and Google Calendar API enabled
- **OAuth 2.0 credentials** (`credentials.json`) from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-email-calendar-assistant.git
cd ai-email-calendar-assistant
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
uv sync

# Create .env file with your Gemini API key
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
```

### 3. Google OAuth Setup

Place your `credentials.json` (downloaded from Google Cloud Console) in the **project root** (`Session-5/`), then generate the OAuth token:

```bash
cd ..  # back to project root
uv run --project backend python backend/generate_token.py
```

This opens a browser window for Google sign-in. Grant access to:
- Gmail (read & send)
- Google Calendar (read & write)

A `token.json` file will be created — **never commit this file**.

### 4. Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the App

Open **two terminals**:

**Terminal 1 — Backend:**
```bash
cd backend
uv run uvicorn server:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## How the Agent Works

The agent follows a simple but powerful loop:

```
User Message
     │
     ▼
┌─────────────┐
│  Iteration   │◄──────────────────────┐
│              │                       │
│  Send to     │                       │
│  Gemini LLM  │                       │
│              │                       │
└──────┬───────┘                       │
       │                               │
       ▼                               │
  ┌──────────┐    ┌──────────────┐     │
  │FINAL_ANS.│    │FUNCTION_CALL │     │
  │          │    │              │     │
  │ Return   │    │ Execute tool │     │
  │ to user  │    │ via MCP      │─────┘
  └──────────┘    │              │  (append result,
                  │ Store result │   loop back)
                  └──────────────┘
```

1. The agent receives a user message and sends it to Gemini with a system prompt listing all 10 available tools.
2. Gemini responds with exactly one line: either `FUNCTION_CALL: tool|params` or `FINAL_ANSWER: text`.
3. If it's a function call, the agent executes it via the MCP server (stdio transport), stores the result, appends it to context, and loops.
4. If it's a final answer, the agent returns the response to the user along with structured context for the side panel.
5. Maximum 5 iterations to prevent infinite loops.

### MCP Tools (10 total)

| # | Tool | Parameters | Purpose |
|---|---|---|---|
| 1 | `get_unread_emails_today` | — | Today's unread emails |
| 2 | `get_emails_by_date_range` | start_date, end_date | Emails within a period |
| 3 | `search_emails` | query (Gmail syntax) | Find emails by sender/topic/keyword |
| 4 | `get_email_thread` | thread_id | Full conversation thread with body text |
| 5 | `get_email_attachments` | message_id | Download & extract text from attachments |
| 6 | `send_email` | to, subject, body | Send an email |
| 7 | `get_todays_events` | — | Today's calendar events |
| 8 | `get_events_for_date` | date | Events on a specific date |
| 9 | `check_free_slots` | date | Free/busy blocks (8 AM – 6 PM) |
| 10 | `create_event` | title, date, start, end, attendees | Create calendar event + send invites |

---

## Future Improvements

- **Conversation Memory** — Persist chat history (SQLite/Redis) so context carries across messages
- **Smart Reply** — Read a thread and draft a context-aware reply ("reply to Sarah saying I agree")
- **Meeting Prep Brief** — "Prepare me for my 2pm meeting" → fetch event details → search emails with attendees → summarize context
- **Daily Briefing** — One command to get unread emails + today's schedule + upcoming deadlines
- **Event Updates/Deletion** — Reschedule or cancel calendar events
- **Multi-User OAuth** — Per-user token storage with session management for multi-tenant deployment
- **Streaming Responses** — Stream agent iterations to the frontend for real-time feedback

---

## License

This project is for educational and portfolio purposes.

---

*Built with Gemini 2.0 Flash, MCP, FastAPI, and React.*
