import { useEffect, useRef } from "react";

/**
 * Scrollable chat message list.
 * Renders "user" and "assistant" bubbles.
 */
function ChatWindow({ messages, loading }) {
  const bottomRef = useRef(null);

  // Auto-scroll to the latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.map((msg) => (
        <div key={msg.id} className={`chat-bubble ${msg.role}`}>
          <div className="chat-role">
            {msg.role === "assistant" ? "Assistant" : "You"}
          </div>
          <div className="chat-text">
            {msg.text.split("\n").map((line, i) => (
              <span key={i}>
                {renderLine(line)}
                {i < msg.text.split("\n").length - 1 && <br />}
              </span>
            ))}
          </div>
        </div>
      ))}

      {loading && (
        <div className="chat-bubble assistant">
          <div className="chat-role">Assistant</div>
          <div className="chat-text typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

/** Minimal bold-text renderer: **text** -> <strong>text</strong> */
function renderLine(line) {
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export default ChatWindow;
