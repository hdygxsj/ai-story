import Bubble from "@ant-design/x/es/bubble";
import Sender from "@ant-design/x/es/sender";
import { Alert, Card, Tag, Typography } from "antd";
import { useState } from "react";

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
  const [pendingConfirmation, setPendingConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(value: string) {
    if (!value.trim()) {
      return;
    }
    setError(null);
    setMessages((current) => [...current, { role: "user", content: message }]);
    setMessage("");
    try {
      const response = await sendAgentMessage(token, novelId, {
        message: value,
        document_id: documentId,
        selected_text: selectedText,
      });
      setPendingConfirmation(response.confirmation?.id ?? null);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.confirmation
            ? `${response.message} Confirmation ${response.confirmation.id} is pending.`
            : response.message,
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent request failed");
    }
  }

  return (
    <Card
      title={
        <Typography.Title level={3} style={{ margin: 0 }}>
          Co-writing Agent
        </Typography.Title>
      }
      extra={pendingConfirmation ? <Tag color="gold">Confirmation pending</Tag> : <Tag color="green">Ready</Tag>}
      style={{ height: "100%" }}
      styles={{ body: { display: "flex", flexDirection: "column", gap: 16, height: "calc(100% - 57px)" } }}
    >
      <Bubble.List
        autoScroll
        items={messages.map((item, index) => ({
          key: `${item.role}-${index}`,
          role: item.role === "assistant" ? "ai" : "user",
          content: item.content,
        }))}
        role={{
          ai: { placement: "start", variant: "shadow" },
          user: { placement: "end", variant: "filled" },
        }}
        style={{ flex: 1 }}
      />
      {error ? <Alert message={error} showIcon type="error" /> : null}
      <Sender
        placeholder="Ask the Agent to plan, rewrite, remember, or inspect context"
        value={message}
        onChange={setMessage}
        onSubmit={handleSend}
      />
    </Card>
  );
}
