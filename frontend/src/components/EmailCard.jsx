/**
 * A single email card for the context panel.
 */
function EmailCard({ email }) {
  // Get the first letter of the sender's name for the avatar
  const initial = (email.from || "?")[0].toUpperCase();

  return (
    <div className="email-card">
      <div className="email-avatar">{initial}</div>
      <div className="email-body">
        <div className="email-from">{email.from}</div>
        <div className="email-subject">{email.subject}</div>
        {email.snippet && (
          <div className="email-snippet">{email.snippet}</div>
        )}
      </div>
    </div>
  );
}

export default EmailCard;
