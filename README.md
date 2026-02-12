# AI Email & Calendar Assistant with RAG

A full-stack agentic AI assistant that manages your Gmail inbox and Google Calendar through natural language. Built with a structured **Perception → Memory → Decision → Action** pipeline, powered by **Google Gemini 2.0 Flash**, with **RAG (Retrieval-Augmented Generation)** for deep document understanding.

> **This is not a ChatGPT wrapper.** The agent autonomously perceives intent, retrieves relevant memory, decides which tools to call, executes them via MCP, stores results, and chains multi-step workflows — all from a single chat interface.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Agent Pipeline](#agent-pipeline)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [File Reference](#file-reference)
- [Use Cases & Examples](#use-cases--examples)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [How the Agent Works](#how-the-agent-works)
- [RAG: Document Search](#rag-document-search)
- [MCP Tools](#mcp-tools)
- [Future Improvements](#future-improvements)

---

## Features

### Email

| Feature | Description |
|---|---|
| **Read Unread Emails** | Fetch and summarize today's unread inbox |
| **Search Emails** | Gmail-syntax search (by sender, subject, date, keyword) |
| **Thread Summarization** | Fetch an entire email thread and summarize the conversation |
| **Attachment Extraction + RAG** | Extract PDF/DOCX text, auto-index in FAISS, and answer questions about the document |
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
| **Perception Layer** | Extracts intent, entities, tool hints, and time references from natural language |
| **Semantic Memory** | In-memory FAISS + Ollama embeddings — remembers tool outputs within a session |
| **Decision Engine** | LLM-based planning with full context from perception + memory |
| **Action Executor** | Parses and executes tool calls via MCP with type-safe argument handling |
| **RAG Pipeline** | Auto-indexes email attachments into FAISS for semantic document search |
| **Multi-Step Reasoning** | Chains up to 5 tool calls to answer complex queries |
| **Context Panel** | Structured side panel shows emails, events, timelines, RAG results alongside chat |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Frontend                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ Chat Window  │  │  Chat Input  │  │     Context Panel     │   │
│  │  (messages)  │  │  (user msg)  │  │ (emails/events/RAG)   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────▲────────────┘   │
└─────────┼─────────────────┼─────────────────────┼────────────────┘
          │          POST /chat                   │
          ▼                 ▼                     │
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Server (server.py)                      │
│                           │                                       │
│                           ▼                                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Agent (agent.py)                         │  │
│  │                                                            │  │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │  │
│  │   │PERCEPTION│→ │  MEMORY  │→ │ DECISION │→ │  ACTION  │ │  │
│  │   │          │  │          │  │          │  │          │ │  │
│  │   │ Intent   │  │ FAISS +  │  │ Gemini   │  │ Execute  │ │  │
│  │   │ Entities │  │ Ollama   │  │ 2.0 Flash│  │ via MCP  │ │  │
│  │   │ Tool hint│  │ Retrieve │  │ Plan     │  │          │ │  │
│  │   └──────────┘  └──────────┘  └──────────┘  └────┬─────┘ │  │
│  │                                                   │       │  │
│  │                    ◄── Memory Store ◄─────────────┘       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                           │ stdio                                 │
│                           ▼                                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                MCP Server (mcp_tools.py)                    │  │
│  │                     11 tools                                │  │
│  └───┬──────────────────┬──────────────────────┬──────────────┘  │
│      │                  │                      │                  │
└──────┼──────────────────┼──────────────────────┼──────────────────┘
       ▼                  ▼                      ▼
┌────────────────┐ ┌───────────────┐ ┌─────────────────────────────┐
│ gmail_client.py│ │calendar_client│ │         rag.py               │
│                │ │               │ │                              │
│  Gmail API     │ │ Calendar API  │ │  ┌───────────────────────┐  │
│  - Read/Search │ │ - Events      │ │  │ PDF / DOCX from Email │  │
│  - Threads     │ │ - Free Slots  │ │  └──────────┬────────────┘  │
│  - Attachments │ │ - Create      │ │             ▼               │
│  - Send        │ │               │ │  ┌───────────────────────┐  │
│                │ │               │ │  │ Text Extract + Clean  │  │
└───────┬────────┘ └───────┬───────┘ │  └──────────┬────────────┘  │
        │                  │         │             ▼               │
        ▼                  ▼         │  ┌───────────────────────┐  │
┌──────────────────────────────────┐ │  │ Chunk (512w, overlap) │  │
│       Google APIs (OAuth 2.0)    │ │  └──────────┬────────────┘  │
│   Gmail API  ·  Calendar API     │ │             ▼               │
└──────────────────────────────────┘ │  ┌───────────────────────┐  │
                                     │  │ Embed (Ollama local)  │  │
                                     │  └──────────┬────────────┘  │
                                     │             ▼               │
                                     │  ┌───────────────────────┐  │
                                     │  │ FAISS Index (on disk) │  │
                                     │  │ index.bin + metadata  │  │
                                     │  └───────────────────────┘  │
                                     └─────────────────────────────┘
```

---

## Agent Pipeline

The agent follows a structured **Perception → Memory → Decision → Action** loop, inspired by cognitive architectures:

```
User Message
     │
     ▼
┌─────────────────────┐
│  1. PERCEPTION       │  Extract intent, entities, tool hints
│     (perception.py)  │  via Gemini LLM
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  2. MEMORY RETRIEVE  │  Semantic search over past tool outputs
│     (memory.py)      │  using FAISS + Ollama embeddings
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  3. DECISION         │  LLM generates: FUNCTION_CALL or FINAL_ANSWER
│     (decision.py)    │  based on perception + memory + tools
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────────┐
│FINAL_ANS.│ │FUNCTION_CALL │
│          │ │              │
│ Return   │ │  4. ACTION   │──── Execute tool via MCP
│ to user  │ │  (action.py) │
└──────────┘ └──────┬───────┘
                    │
                    ▼
           ┌──────────────┐
           │5. MEMORY STORE│──── Save tool result
           └──────┬───────┘
                  │
                  ▼
            Loop back to
            step 2 (max 5)
```

### Why This Architecture?

| Layer | Purpose | Benefit |
|-------|---------|---------|
| **Perception** | Structured understanding of user intent | The decision LLM gets pre-processed context instead of raw text |
| **Memory** | Semantic retrieval of past tool outputs | Agent "remembers" what it did in previous steps and chats |
| **Decision** | LLM-based planning with full context | Accurate tool selection with awareness of available tools, past results, and user intent |
| **Action** | Type-safe tool execution via MCP | Clean separation between planning and execution |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 6 |
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **AI Model** | Google Gemini 2.0 Flash |
| **Tool Protocol** | Model Context Protocol (MCP) via FastMCP |
| **Embeddings** | Ollama (nomic-embed-text) — runs locally |
| **Vector Search** | FAISS (faiss-cpu) |
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
│   │
│   │  ── Agent Pipeline ──
│   ├── agent.py                # Orchestrator — perception → memory → decision → action loop
│   ├── perception.py           # Step 1: Extract intent, entities, tool hints via LLM
│   ├── memory.py               # Step 2: In-memory FAISS + Ollama semantic memory
│   ├── decision.py             # Step 3: LLM-based planning (FUNCTION_CALL / FINAL_ANSWER)
│   ├── action.py               # Step 4: Parse and execute tool calls via MCP
│   │
│   │  ── Server & Tools ──
│   ├── server.py               # FastAPI HTTP server
│   ├── mcp_tools.py            # MCP server — exposes 11 tools (Gmail + Calendar + RAG)
│   │
│   │  ── API Clients ──
│   ├── gmail_client.py         # Gmail API client functions
│   ├── calendar_client.py      # Google Calendar API client functions
│   │
│   │  ── RAG ──
│   ├── rag.py                  # FAISS document indexer (chunk → embed → store → search)
│   ├── rag_index/              # Auto-generated: FAISS index + metadata (persisted to disk)
│   │
│   │  ── Setup ──
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

### Backend — Agent Pipeline

| File | Responsibility | Key Functions |
|---|---|---|
| `agent.py` | Orchestrator — runs the perception → memory → decision → action loop | `handle_chat()`, `_build_context()`, `_format_tool_descriptions()` |
| `perception.py` | Extracts structured intent, entities, tool hints, time references from user input using Gemini | `extract_perception()` → returns `PerceptionResult` |
| `memory.py` | In-memory semantic memory using FAISS + Ollama embeddings. Stores/retrieves tool outputs and user queries | `MemoryManager.add()`, `MemoryManager.retrieve()` |
| `decision.py` | LLM-based planner — takes perception + memory + tool descriptions → produces FUNCTION_CALL or FINAL_ANSWER | `generate_plan()` |
| `action.py` | Parses FUNCTION_CALL strings, matches params to tool schemas, executes via MCP session | `execute_tool()`, `parse_function_call()` → returns `ToolCallResult` |

### Backend — Server & Tools

| File | Responsibility | Key Functions |
|---|---|---|
| `server.py` | FastAPI HTTP layer — receives requests from frontend, routes to agent | `GET /`, `GET /emails/unread-today`, `POST /chat` |
| `mcp_tools.py` | MCP server — wraps Gmail/Calendar/RAG functions as 11 tools (stdio transport) | 11 `@mcp.tool()` functions |

### Backend — API Clients & RAG

| File | Responsibility | Key Functions |
|---|---|---|
| `gmail_client.py` | Gmail API — all direct interactions with Gmail | `get_unread_emails_today()`, `search_emails()`, `get_email_thread()`, `get_email_attachments()`, `send_email()`, `get_emails_by_date_range()` |
| `calendar_client.py` | Calendar API — all direct interactions with Google Calendar | `get_todays_events()`, `get_events_for_date()`, `check_free_slots()`, `create_event()` |
| `rag.py` | FAISS document indexer — chunks text, embeds via Ollama, stores/searches on disk | `index_document()`, `search_documents()`, `chunk_text()` |
| `generate_token.py` | One-time script to run Google OAuth and save `token.json` | Run once during setup |

### Frontend

| File | Responsibility |
|---|---|
| `App.jsx` | Main layout — manages messages state, calls API, renders two-column layout |
| `ChatWindow.jsx` | Displays chat messages with auto-scroll and typing indicator |
| `ChatInput.jsx` | User input field with send button |
| `QuickActions.jsx` | Quick-action buttons (e.g., "Summarize unread emails") |
| `ContextPanel.jsx` | Renders structured data in the side panel based on context type (emails, events, threads, attachments, RAG results, free slots) |
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
| "Send an email to john@example.com saying I'll be late" | Crafts a polite email → calls `send_email` |

### Calendar Management

| You say | What the agent does |
|---|---|
| "What's on my schedule today?" | Calls `get_todays_events` → shows event cards in panel |
| "Do I have meetings on Feb 12th?" | Calls `get_events_for_date\|2026-02-12` |
| "Am I free Thursday afternoon?" | Calls `check_free_slots` → shows visual timeline |
| "Schedule a dentist appointment on March 5th from 2 to 3 PM" | Calls `create_event` → shows confirmation card with Google Calendar link |
| "Set up a meeting with sarah@co.com tomorrow at 10" | Creates event with attendee → Google sends invite automatically |

### RAG — Document Understanding

| You say | Agent steps |
|---|---|
| "Read me dhruv's latest document" | 1. `search_emails\|from:dhruv has:attachment` → 2. `get_email_attachments` (auto-indexes PDF in FAISS) → 3. Summarizes from preview |
| "Explain transformer from that document" | 1. `search_indexed_documents\|transformer` → retrieves relevant chunks → 2. Explains based on document content |
| "What does the document say about hallucination?" | 1. `search_indexed_documents\|hallucination` → FAISS returns top-5 chunks → 2. Synthesizes answer |

### Multi-Step (Agentic)

| You say | Agent steps |
|---|---|
| "Summarize the document sent by dhruv" | 1. Search emails with attachment → 2. Extract PDF + auto-index → 3. Summarize content |
| "What did sarah and I discuss last week?" | 1. Search emails from/to sarah → 2. Fetch thread → 3. Summarize conversation |

---

## Setup & Installation

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **uv** (Python package manager) — [install guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Ollama** (local embeddings for Memory + RAG) — [download](https://ollama.com/download)
- **Google Cloud Project** with Gmail API and Google Calendar API enabled
- **OAuth 2.0 credentials** (`credentials.json`) from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### 1. Clone the Repository

```bash
git clone https://github.com/dhruvLearner8/Personal-AI-Agent-for-GMail-and-Calendar-Assistant.git
cd Personal-AI-Agent-for-GMail-and-Calendar-Assistant
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
uv sync

# Create .env file with your Gemini API key
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
```

### 3. Ollama Setup (for Memory + RAG)

```bash
# Install Ollama from https://ollama.com/download, then:
ollama pull nomic-embed-text

# Verify it's running
ollama list
```

Ollama runs a local server on `http://localhost:11434`. The `nomic-embed-text` model is used for:
- **Memory** — Embedding tool outputs for semantic retrieval within a session
- **RAG** — Embedding document chunks for similarity search over email attachments

### 4. Google OAuth Setup

Place your `credentials.json` (downloaded from Google Cloud Console) in the **project root**, then generate the OAuth token:

```bash
cd ..  # back to project root
uv run --project backend python backend/generate_token.py
```

This opens a browser window for Google sign-in. Grant access to:
- Gmail (read & send)
- Google Calendar (read & write)

A `token.json` file will be created — **never commit this file**.

### 5. Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the App

Open **two terminals** + make sure Ollama is running:

**Terminal 0 — Ollama (if not auto-started):**
```bash
ollama serve
```

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

### The Loop

1. User sends a message via the React frontend
2. Frontend sends `POST /chat` to FastAPI
3. **Perception** — Gemini extracts intent, entities, tool hints from the message
4. **Memory Retrieve** — FAISS semantic search finds relevant past tool outputs
5. **Decision** — Gemini receives perception + memory + tool list → outputs `FUNCTION_CALL: tool|params` or `FINAL_ANSWER: text`
6. **Action** — If FUNCTION_CALL, the agent executes it via MCP (stdio), stores the result
7. **Memory Store** — Tool output is embedded and added to in-memory FAISS index
8. Loop back to step 4 with updated context (max 5 iterations)
9. On FINAL_ANSWER, return `{reply, context}` to the frontend
10. Frontend renders the chat reply + structured data in the side panel

### Perception Output Example

```json
{
  "user_input": "Show me emails from dhruv about the project",
  "intent": "search_email",
  "entities": ["dhruv", "project"],
  "tool_hint": "search_emails",
  "time_refs": []
}
```

### Decision Output Example

```
FUNCTION_CALL: search_emails|from:dhruv subject:project
```

---

## RAG: Document Search

When the agent fetches email attachments (via `get_email_attachments`), large documents (>500 chars) are **automatically indexed** into a local FAISS vector database:

```
PDF/DOCX from email
        │
        ▼
┌──────────────────┐
│  Text Extraction  │  PyPDF2 / python-docx
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Text Cleaning    │  Strip non-ASCII, collapse whitespace
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Chunking         │  512 words, 40-word overlap
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Embedding        │  Ollama nomic-embed-text (local)
└────────┬─────────┘
         ▼
┌──────────────────┐
│  FAISS Index      │  Persisted to disk (rag_index/)
└──────────────────┘
```

Once indexed, the user can ask follow-up questions about the document:

```
User: "What does the document say about tokenization?"
  → search_indexed_documents|tokenization
  → FAISS returns top-5 relevant chunks
  → LLM synthesizes answer from chunks
```

**Key details:**
- Embeddings are generated **locally** via Ollama — no data leaves your machine
- FAISS index persists to disk (`rag_index/index.bin` + `metadata.json`)
- Duplicate documents are detected by title and skipped
- Text is cleaned of non-printable characters before embedding

---

## MCP Tools (11 total)

| # | Tool | Parameters | Purpose |
|---|---|---|---|
| 1 | `get_unread_emails_today` | — | Today's unread emails |
| 2 | `get_emails_by_date_range` | start_date, end_date | Emails within a period |
| 3 | `search_emails` | query (Gmail syntax) | Find emails by sender/topic/keyword |
| 4 | `get_email_thread` | thread_id | Full conversation thread with body text |
| 5 | `get_email_attachments` | message_id | Extract text from attachments + auto-index for RAG |
| 6 | `send_email` | to, subject, body | Send an email |
| 7 | `get_todays_events` | — | Today's calendar events |
| 8 | `get_events_for_date` | date | Events on a specific date |
| 9 | `check_free_slots` | date | Free/busy blocks (8 AM – 6 PM) |
| 10 | `create_event` | title, date, start, end, attendees | Create calendar event + send invites |
| 11 | `search_indexed_documents` | query | Semantic search over indexed email attachments (RAG) |

---

## Future Improvements

- **Persistent Conversation Memory** — Save chat history to SQLite/Redis so context carries across server restarts
- **Keyword-Based Perception** — Replace LLM perception with fast regex/keyword classification to reduce API calls
- **Smart Reply** — Read a thread and draft a context-aware reply ("reply to Sarah saying I agree")
- **Meeting Prep Brief** — "Prepare me for my 2pm meeting" → fetch event details → search emails with attendees → summarize context
- **Daily Briefing** — One command to get unread emails + today's schedule + upcoming deadlines
- **Event Updates/Deletion** — Reschedule or cancel calendar events
- **Streaming Responses** — Stream agent iterations to the frontend for real-time feedback
- **Multi-Document RAG** — Search across multiple indexed documents simultaneously

---

## License

This project is for educational and portfolio purposes.

---

*Built with Gemini 2.0 Flash, MCP, FAISS, Ollama, FastAPI, and React.*
