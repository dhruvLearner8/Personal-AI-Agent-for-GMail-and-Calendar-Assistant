/**
 * API layer — all backend calls live here.
 * The Vite dev-server proxies /emails/* and /chat to localhost:8000.
 */

const BASE = "";

/**
 * Fetch today's unread emails from Gmail via the backend.
 */
export async function fetchUnreadToday() {
  const res = await fetch(`${BASE}/emails/unread-today`);
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  return res.json();
}

/**
 * Send a list of emails to the stub summariser.
 */
export async function summarizeEmails(emails) {
  const res = await fetch(`${BASE}/emails/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ emails }),
  });
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  return res.json();
}

/**
 * Send a chat message to the agent.
 * Returns { reply: string, context: { type: string, data: any } | null }
 */
export async function sendChatMessage(message) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  return res.json();
}
