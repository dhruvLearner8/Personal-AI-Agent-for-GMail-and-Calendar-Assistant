/**
 * A single calendar event card for the context panel.
 */
function EventCard({ event }) {
  const startTime = formatTime(event.start);
  const endTime = formatTime(event.end);

  return (
    <div className="event-card">
      <div className="event-time">
        {startTime} &mdash; {endTime}
      </div>
      <div className="event-title">{event.summary}</div>
      {event.location && (
        <div className="event-meta">
          <span>&#128205;</span> {event.location}
        </div>
      )}
      {event.attendees && event.attendees.length > 0 && (
        <div className="event-meta">
          <span>&#128101;</span> {event.attendees.join(", ")}
        </div>
      )}
    </div>
  );
}

/** Parse ISO datetime or HH:MM into a readable time string */
function formatTime(raw) {
  if (!raw) return "";
  try {
    // If it's an ISO string like "2026-02-07T09:00:00"
    if (raw.includes("T")) {
      const d = new Date(raw);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return raw;
  } catch {
    return raw;
  }
}

export default EventCard;
