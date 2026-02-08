import EventCard from "./EventCard";
import EmailCard from "./EmailCard";
import FreeSlotTimeline from "./FreeSlotTimeline";

/**
 * Side panel that shows structured data from the agent's tool calls.
 * Renders different card layouts based on context type.
 */
function ContextPanel({ data }) {
  if (!data) {
    return (
      <div className="context-panel empty">
        <div className="context-empty">
          <span className="context-empty-icon">&#128202;</span>
          <p>Ask about your schedule or emails to see details here.</p>
        </div>
      </div>
    );
  }

  const { type, data: items } = data;

  // Calendar events
  if (type === "calendar_events") {
    if (!items || items.length === 0) {
      return (
        <div className="context-panel">
          <h2 className="context-title">&#128197; Schedule</h2>
          <p className="context-empty-text">No events found.</p>
        </div>
      );
    }
    return (
      <div className="context-panel">
        <h2 className="context-title">&#128197; Schedule</h2>
        <div className="context-list">
          {items.map((event, i) => (
            <EventCard key={i} event={event} />
          ))}
        </div>
      </div>
    );
  }

  // Free / busy slots
  if (type === "free_slots") {
    return (
      <div className="context-panel">
        <h2 className="context-title">&#9200; Availability</h2>
        <FreeSlotTimeline data={items} />
      </div>
    );
  }

  // Event created confirmation
  if (type === "event_created") {
    return (
      <div className="context-panel">
        <h2 className="context-title">&#9989; Event Created</h2>
        <div className="created-card">
          <div className="created-title">{items.summary || items.title}</div>
          <div className="created-detail">
            <span>&#128197;</span> {items.date}
          </div>
          <div className="created-detail">
            <span>&#128336;</span> {items.start} &mdash; {items.end}
          </div>
          {items.link && (
            <a
              className="created-link"
              href={items.link}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open in Google Calendar &rarr;
            </a>
          )}
        </div>
      </div>
    );
  }

  // Email list
  if (type === "email_list") {
    if (!items || items.length === 0) {
      return (
        <div className="context-panel">
          <h2 className="context-title">&#9993; Emails</h2>
          <p className="context-empty-text">No unread emails today.</p>
        </div>
      );
    }
    return (
      <div className="context-panel">
        <h2 className="context-title">&#9993; Emails ({items.length})</h2>
        <div className="context-list">
          {items.map((email, i) => (
            <EmailCard key={i} email={email} />
          ))}
        </div>
      </div>
    );
  }

  // Email thread (full conversation)
  if (type === "email_thread") {
    const messages = items.messages || [];
    return (
      <div className="context-panel">
        <h2 className="context-title">&#128172; Thread: {items.subject || "Conversation"}</h2>
        <p className="thread-meta">{items.message_count || messages.length} messages</p>
        <div className="context-list thread-list">
          {messages.map((msg, i) => (
            <div key={i} className="thread-message-card">
              <div className="thread-msg-header">
                <span className="thread-msg-from">{msg.from?.split("<")[0]?.trim()}</span>
                <span className="thread-msg-date">{msg.date?.split(",").slice(0, 2).join(",")}</span>
              </div>
              <div className="thread-msg-body">{msg.body?.substring(0, 300)}{msg.body?.length > 300 ? "..." : ""}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Email attachments
  if (type === "email_attachments") {
    const attachments = items.attachments || [];
    return (
      <div className="context-panel">
        <h2 className="context-title">&#128206; Attachments from: {items.subject || "Email"}</h2>
        <p className="thread-meta">From: {items.from} &middot; {attachments.length} file{attachments.length !== 1 ? "s" : ""}</p>
        <div className="context-list">
          {attachments.map((att, i) => (
            <div key={i} className="attachment-card">
              <div className="attachment-header">
                <span className="attachment-icon">
                  {att.filename?.endsWith(".pdf") ? "\uD83D\uDCC4" : att.filename?.endsWith(".docx") ? "\uD83D\uDCC3" : "\uD83D\uDCCE"}
                </span>
                <div className="attachment-meta">
                  <span className="attachment-name">{att.filename}</span>
                  <span className="attachment-size">{att.mime_type} &middot; {(att.size / 1024).toFixed(1)} KB</span>
                </div>
              </div>
              <div className="attachment-content">{att.content?.substring(0, 500)}{att.content?.length > 500 ? "..." : ""}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Email sent confirmation
  if (type === "email_sent") {
    return (
      <div className="context-panel">
        <h2 className="context-title">&#9989; Email Sent</h2>
        <div className="created-card">
          <div className="created-title">To: {items.to}</div>
          <div className="created-detail">
            <span>&#9993;</span> {items.subject}
          </div>
          {items.status === "sent" && (
            <div className="created-detail" style={{ color: "var(--green)" }}>
              <span>&#10003;</span> Delivered successfully
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}

export default ContextPanel;
