import Bubble from "@ant-design/x/es/bubble";
import Sender from "@ant-design/x/es/sender";
import { CloseOutlined, PushpinOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Flex, Space, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import type { WorkspaceDiff } from "../../api/agent";
import { sendAgentMessage } from "../../api/agent";
import type { WorkspaceNode } from "../../api/workspace";

type AgentPanelProps = {
  token: string;
  novelId: string;
  documentId?: string | null;
  onClearSelectedText?: () => void;
  onUndoWorkspaceDiff?: () => void;
  onWorkspaceOrganized?: (nodes: WorkspaceNode[], diff: WorkspaceDiff) => void;
  rewriteRequest?: { id: number; text: string } | null;
  selectedText?: string | null;
  workspaceDiff?: WorkspaceDiff | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export function AgentPanel({
  token,
  novelId,
  documentId,
  onClearSelectedText,
  onUndoWorkspaceDiff,
  onWorkspaceOrganized,
  rewriteRequest,
  selectedText,
  workspaceDiff,
}: AgentPanelProps) {
  const [message, setMessage] = useState("请帮我改写选中的段落，让张力更强。");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "告诉我你想创建、改写、记录或检索什么。" },
  ]);
  const [pendingConfirmation, setPendingConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(value: string, overrideSelectedText?: string | null) {
    if (!value.trim()) {
      return;
    }
    setError(null);
    setMessages((current) => [...current, { role: "user", content: value }]);
    setMessage("");
    try {
      const response = await sendAgentMessage(token, novelId, {
        message: value,
        document_id: documentId,
        selected_text: overrideSelectedText ?? selectedText,
      });
      if (response.workspace_diff && response.workspace_nodes) {
        onWorkspaceOrganized?.(response.workspace_nodes, response.workspace_diff);
      }
      setPendingConfirmation(response.confirmation?.id ?? null);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.confirmation
            ? `${response.message} 确认项 ${response.confirmation.id} 正在等待处理。`
            : response.message,
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent 请求失败");
    }
  }

  async function handleSend(value: string) {
    await sendMessage(value);
  }

  async function handleQuoteAction(action: "analyze" | "rewrite" | "polish") {
    const promptByAction = {
      analyze: "请解析这段引用，指出它在剧情、人物和节奏上的问题。",
      rewrite: "请改写这段引用，保持上下文风格并提升表达质量。",
      polish: "请润色这段引用，让语言更有画面感和文学性。",
    };
    await sendMessage(promptByAction[action], selectedText);
  }

  useEffect(() => {
    if (!rewriteRequest?.text) {
      return;
    }

    void sendMessage("请改写我刚刚选中的这段文字，保持上下文风格并提升表达质量。", rewriteRequest.text);
  }, [rewriteRequest?.id]);

  return (
    <Card
      title={
        <Typography.Title level={3} style={{ margin: 0 }}>
          共创 Agent
        </Typography.Title>
      }
      extra={pendingConfirmation ? <Tag color="gold">等待确认</Tag> : <Tag color="green">就绪</Tag>}
      style={{
        background: "rgba(255,255,255,0.82)",
        border: "1px solid rgba(15,23,42,0.06)",
        boxShadow: "0 18px 58px rgba(15,23,42,0.08)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
        minWidth: 0,
      }}
      styles={{ body: { display: "flex", flex: 1, flexDirection: "column", gap: 16, minHeight: 0, overflow: "hidden" } }}
    >
      <div data-testid="agent-message-scroll" style={{ flex: "1 1 0", minHeight: 0, overflow: "auto" }}>
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
          style={{ minHeight: 0 }}
        />
      </div>
      {error ? <Alert message={error} showIcon style={{ flexShrink: 0 }} type="error" /> : null}
      {workspaceDiff ? (
        <div
          aria-label="Agent 目录变更"
          style={{
            background: "#fff7ed",
            border: "1px solid rgba(249,115,22,0.24)",
            borderRadius: 16,
            flexShrink: 0,
            padding: 12,
          }}
        >
          <Flex align="center" justify="space-between" gap={8}>
            <Typography.Text strong>{workspaceDiff.summary}</Typography.Text>
            <Button size="small" onClick={onUndoWorkspaceDiff}>
              撤销本次整理
            </Button>
          </Flex>
          <Space direction="vertical" size={4} style={{ marginTop: 8, width: "100%" }}>
            {workspaceDiff.changes.map((change) => (
              <Typography.Text key={`${change.action}-${change.node_id}`} type="secondary">
                {change.action === "move" ? "移动" : change.action}：{change.title}
              </Typography.Text>
            ))}
          </Space>
        </div>
      ) : null}
      {selectedText ? (
        <div
          aria-label="Agent 引用卡"
          style={{
            background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
            border: "1px solid rgba(99,91,255,0.18)",
            borderRadius: 16,
            boxShadow: "0 14px 36px rgba(15,23,42,0.10)",
            flexShrink: 0,
            padding: 12,
          }}
        >
          <Flex align="center" justify="space-between">
            <Space size={8}>
              <PushpinOutlined style={{ color: "#635bff" }} />
              <Typography.Text strong>已引用选中段落</Typography.Text>
              <Tag color="purple">来自正文</Tag>
            </Space>
            <Button
              aria-label="移除引用"
              icon={<CloseOutlined />}
              onClick={onClearSelectedText}
              shape="circle"
              size="small"
              type="text"
            />
          </Flex>
          <Typography.Paragraph
            ellipsis={{ rows: 2 }}
            style={{
              background: "#f5f7fb",
              borderLeft: "3px solid #635bff",
              borderRadius: 10,
              color: "#374151",
              margin: "10px 0",
              padding: "8px 10px",
            }}
          >
            {selectedText}
          </Typography.Paragraph>
          <Space wrap>
            <Button size="small" onClick={() => void handleQuoteAction("analyze")}>
              解析引用
            </Button>
            <Button size="small" type="primary" onClick={() => void handleQuoteAction("rewrite")}>
              改写引用
            </Button>
            <Button size="small" onClick={() => void handleQuoteAction("polish")}>
              润色引用
            </Button>
          </Space>
        </div>
      ) : null}
      <div data-testid="agent-input-shell" style={{ flexShrink: 0 }}>
        <Sender
          placeholder="让 Agent 规划、改写、记录记忆或检索上下文"
          value={message}
          onChange={setMessage}
          onSubmit={handleSend}
        />
      </div>
    </Card>
  );
}
