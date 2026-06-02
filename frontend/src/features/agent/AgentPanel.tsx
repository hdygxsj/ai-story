import { FormEvent, useState } from "react";

import { sendAgentMessage } from "../../api/agent";

type AgentPanelProps = {
  token: string;
  novelId: string;
  documentId?: string | null;
  selectedText?: string | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export function AgentPanel({ token, novelId, documentId, selectedText }: AgentPanelProps) {
  const [message, setMessage] = useState("Rewrite the selected paragraph to feel more tense.");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Tell me what to create, rewrite, or remember." },
  ]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessages((current) => [...current, { role: "user", content: message }]);
    const response = await sendAgentMessage(token, novelId, {
      message,
      document_id: documentId,
      selected_text: selectedText,
    });
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        content: response.confirmation
          ? `${response.message} Confirmation ${response.confirmation.id} is pending.`
          : response.message,
      },
    ]);
  }

  return (
    <aside style={{ borderLeft: "1px solid #ddd", display: "grid", gap: 12, padding: 16 }}>
      <h2>Agent</h2>
      <div aria-label="Agent conversation" style={{ display: "grid", gap: 8 }}>
        {messages.map((item, index) => (
          <p key={`${item.role}-${index}`}>
            <strong>{item.role}:</strong> {item.content}
          </p>
        ))}
      </div>
      <form onSubmit={handleSend} style={{ display: "grid", gap: 8 }}>
        <textarea
          aria-label="Agent message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <button type="submit">Send</button>
      </form>
    </aside>
  );
}
