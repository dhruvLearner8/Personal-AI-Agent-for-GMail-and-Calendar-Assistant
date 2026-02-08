/**
 * Quick-action buttons — sits between the chat window and the text input.
 */
function QuickActions({ onSummarize, disabled }) {
  return (
    <div className="quick-actions">
      <button
        className="action-btn"
        onClick={onSummarize}
        disabled={disabled}
      >
        <span className="action-icon">&#128231;</span>
        Summarize unread emails (today)
      </button>
    </div>
  );
}

export default QuickActions;
