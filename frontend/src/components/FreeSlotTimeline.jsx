/**
 * Visual free/busy timeline for the context panel.
 */
function FreeSlotTimeline({ data }) {
  if (!data) return null;

  const { date, busy = [], free = [] } = data;

  return (
    <div className="timeline">
      {date && <div className="timeline-date">{date}</div>}

      {busy.length > 0 && (
        <div className="timeline-section">
          <h3 className="timeline-heading busy-heading">Busy</h3>
          {busy.map((slot, i) => (
            <div key={i} className="timeline-slot busy-slot">
              <span className="slot-dot busy-dot"></span>
              {slot.start} &mdash; {slot.end}
            </div>
          ))}
        </div>
      )}

      {free.length > 0 && (
        <div className="timeline-section">
          <h3 className="timeline-heading free-heading">Free</h3>
          {free.map((slot, i) => (
            <div key={i} className="timeline-slot free-slot">
              <span className="slot-dot free-dot"></span>
              {slot.start} &mdash; {slot.end}
            </div>
          ))}
        </div>
      )}

      {busy.length === 0 && free.length === 0 && (
        <p className="context-empty-text">No availability data found.</p>
      )}
    </div>
  );
}

export default FreeSlotTimeline;
