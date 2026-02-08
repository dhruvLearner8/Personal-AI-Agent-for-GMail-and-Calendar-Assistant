import { useState, useCallback } from "react";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import QuickActions from "./components/QuickActions";
import ContextPanel from "./components/ContextPanel";
import { fetchUnreadToday, summarizeEmails, sendChatMessage } from "./api";

function App() {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Hi! I'm your AI Email & Calendar Assistant. Ask me about your schedule, emails, or use the quick actions below.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [contextData, setContextData] = useState(null);

  const addMessage = useCallback((role, text) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, text },
    ]);
  }, []);

  /** Handle the "Summarize unread emails" quick-action */
  const handleSummarize = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    addMessage("user", "Summarize my unread emails from today.");

    try {
      addMessage("assistant", "Fetching your unread emails...");
      const { emails, error } = await fetchUnreadToday();

      if (error) {
        addMessage("assistant", `Error: ${error}`);
        setLoading(false);
        return;
      }

      if (emails.length === 0) {
        addMessage("assistant", "You have no unread emails today. Inbox zero!");
        setContextData({ type: "email_list", data: [] });
        setLoading(false);
        return;
      }

      const list = emails
        .map((e) => `- **${e.subject}** from ${e.from}`)
        .join("\n");
      addMessage(
        "assistant",
        `Found ${emails.length} unread email${emails.length !== 1 ? "s" : ""}:\n${list}`
      );
      setContextData({ type: "email_list", data: emails });

      addMessage("assistant", "Generating summary...");
      const { summary } = await summarizeEmails(emails);
      addMessage("assistant", summary);
    } catch (err) {
      addMessage("assistant", `Something went wrong: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [loading, addMessage]);

  /** Handle plain text messages — send to the agent */
  const handleSend = useCallback(
    async (text) => {
      if (!text.trim() || loading) return;
      addMessage("user", text);
      setLoading(true);
      try {
        const { reply, context } = await sendChatMessage(text);
        addMessage("assistant", reply);
        if (context) {
          setContextData(context);
        }
      } catch (err) {
        addMessage("assistant", `Something went wrong: ${err.message}`);
      } finally {
        setLoading(false);
      }
    },
    [loading, addMessage]
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">&#9993;</span>
          <h1>Email & Calendar Assistant</h1>
        </div>
        <span className="badge">v0.2 &mdash; agentic</span>
      </header>

      <div className="app-body">
        {/* Left — Chat */}
        <main className="app-main">
          <ChatWindow messages={messages} loading={loading} />
          <QuickActions onSummarize={handleSummarize} disabled={loading} />
          <ChatInput onSend={handleSend} disabled={loading} />
        </main>

        {/* Right — Context Panel */}
        <aside className="app-sidebar">
          <ContextPanel data={contextData} />
        </aside>
      </div>
    </div>
  );
}

export default App;
