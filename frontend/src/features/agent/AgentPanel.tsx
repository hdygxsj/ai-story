import Bubble from "@ant-design/x/es/bubble";
import Sender from "@ant-design/x/es/sender";
import { CloseOutlined, PushpinOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Flex, Space, Tag, Typography } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ContextDetail, WorkspaceDiff } from "../../api/agent";
import { streamAgentMessage } from "../../api/agent";
import type { Conversation } from "../../api/conversations";
import {
  createConversation,
  deleteConversation,
  listConversationMessages,
  listConversations,
  updateConversation,
} from "../../api/conversations";
import type { WorkspaceNode } from "../../api/workspace";
import { AgentMarkdown } from "./AgentMarkdown";
import { ContextSettingsDrawer } from "./ContextSettingsDrawer";
import { ContextStatusBar } from "./ContextStatusBar";
import { ConversationSidebar } from "./ConversationSidebar";
import "./agent-panel.css";

type AgentPanelProps = {
  hasModelProfile?: boolean;
  onOpenModelConfig?: () => void;
  token: string;
  novelId: string;
  documentId?: string | null;
  onClearSelectedText?: () => void;
  onDismissWorkspaceDiff?: () => void;
  onRunCompleted?: () => void | Promise<void>;
  onUndoWorkspaceDiff?: () => void;
  onWorkspaceOrganized?: (nodes: WorkspaceNode[], diff?: WorkspaceDiff | null) => void;
  rewriteRequest?: { id: number; text: string } | null;
  selectedText?: string | null;
  workspaceDiff?: WorkspaceDiff | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const WELCOME_MESSAGE = "告诉我你想创建、改写、记录或检索什么。";

function createMessageId(role: ChatMessage["role"]) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function welcomeMessages(): ChatMessage[] {
  return [{ id: createMessageId("assistant"), role: "assistant", content: WELCOME_MESSAGE }];
}

export function AgentPanel({
  hasModelProfile = true,
  onOpenModelConfig,
  token,
  novelId,
  documentId,
  onClearSelectedText,
  onDismissWorkspaceDiff,
  onRunCompleted,
  onUndoWorkspaceDiff,
  onWorkspaceOrganized,
  rewriteRequest,
  selectedText,
  workspaceDiff,
}: AgentPanelProps) {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(welcomeMessages);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [contextDetail, setContextDetail] = useState<ContextDetail | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const activeAssistantIdRef = useRef<string | null>(null);

  const refreshConversations = useCallback(async () => {
    const items = await listConversations(token, novelId);
    setConversations(items);
    return items;
  }, [novelId, token]);

  const loadConversationMessages = useCallback(
    async (conversationId: string) => {
      const stored = await listConversationMessages(token, novelId, conversationId);
      if (stored.length === 0) {
        setMessages(welcomeMessages());
        return;
      }
      setMessages(
        stored.map((item) => ({
          id: item.id,
          role: item.role === "user" ? "user" : "assistant",
          content: item.content,
        })),
      );
    },
    [novelId, token],
  );

  useEffect(() => {
    void refreshConversations().catch((caught: Error) => setError(caught.message));
  }, [refreshConversations]);

  function appendAssistantContent(assistantId: string, delta: string) {
    setMessages((current) =>
      current.map((item) =>
        item.id === assistantId ? { ...item, content: `${item.content}${delta}` } : item,
      ),
    );
  }

  function finalizeAssistantMessage(assistantId: string, content: string) {
    setMessages((current) =>
      current.map((item) => (item.id === assistantId ? { ...item, content } : item)),
    );
  }

  async function sendMessage(value: string, overrideSelectedText?: string | null) {
    if (!value.trim() || streaming) {
      return;
    }
    setError(null);
    setStreaming(true);

    const assistantId = createMessageId("assistant");
    activeAssistantIdRef.current = assistantId;
    setMessages((current) => [
      ...current.filter((item) => item.content !== WELCOME_MESSAGE || item.role !== "assistant"),
      { id: createMessageId("user"), role: "user", content: value },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setMessage("");

    await streamAgentMessage(
      token,
      novelId,
      {
        message: value,
        document_id: documentId,
        selected_text: overrideSelectedText ?? selectedText,
        conversation_id: activeConversationId,
      },
      {
        onDelta: (content) => {
          appendAssistantContent(assistantId, content);
        },
        onDone: (payload) => {
          if (payload.workspace_nodes) {
            onWorkspaceOrganized?.(payload.workspace_nodes, payload.workspace_diff);
          }
          if (payload.conversation_id) {
            setActiveConversationId(payload.conversation_id);
          }
          setContextDetail(payload.context_detail ?? null);
          setPendingConfirmation(payload.confirmation?.id ?? null);
          const finalMessage = payload.confirmation
            ? `${payload.message} 确认项 ${payload.confirmation.id} 正在等待处理。`
            : payload.message;
          finalizeAssistantMessage(assistantId, finalMessage);
          setStreaming(false);
          activeAssistantIdRef.current = null;
          try {
            void Promise.resolve(onRunCompleted?.()).catch(() => undefined);
          } catch {
            // The completed Agent response remains usable if a background refresh fails.
          }
          void refreshConversations().catch(() => undefined);
        },
        onError: (caught) => {
          setError(caught.message);
          finalizeAssistantMessage(assistantId, caught.message);
          setStreaming(false);
          activeAssistantIdRef.current = null;
        },
      },
    );
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

  async function handleCreateConversation() {
    const created = await createConversation(token, novelId);
    setActiveConversationId(created.id);
    setMessages(welcomeMessages());
    await refreshConversations();
  }

  async function handleSelectConversation(conversationId: string) {
    setActiveConversationId(conversationId);
    await loadConversationMessages(conversationId);
  }

  async function handleRenameConversation(conversationId: string, title: string) {
    await updateConversation(token, novelId, conversationId, title);
    await refreshConversations();
  }

  async function handleDeleteConversation(conversationId: string) {
    await deleteConversation(token, novelId, conversationId);
    const remaining = await refreshConversations();
    if (activeConversationId === conversationId) {
      if (remaining[0]) {
        setActiveConversationId(remaining[0].id);
        await loadConversationMessages(remaining[0].id);
      } else {
        setActiveConversationId(null);
        setMessages(welcomeMessages());
      }
    }
  }

  useEffect(() => {
    if (!rewriteRequest?.text) {
      return;
    }

    void sendMessage("请改写我刚刚选中的这段文字，保持上下文风格并提升表达质量。", rewriteRequest.text);
  }, [rewriteRequest?.id]);

  return (
    <Card
      className="agent-panel-card"
      title={
        <div className="agent-panel-header" data-testid="agent-panel-header">
          <Typography.Title level={4} style={{ margin: 0, whiteSpace: "nowrap" }}>
            共创 Agent
          </Typography.Title>
          <ConversationSidebar
            activeConversationId={activeConversationId}
            conversations={conversations}
            disabled={streaming}
            onCreateConversation={() => void handleCreateConversation().catch((caught: Error) => setError(caught.message))}
            onDeleteConversation={(conversationId) =>
              void handleDeleteConversation(conversationId).catch((caught: Error) => setError(caught.message))
            }
            onOpenContextSettings={() => setSettingsOpen(true)}
            onRenameConversation={(conversationId, title) =>
              void handleRenameConversation(conversationId, title).catch((caught: Error) => setError(caught.message))
            }
            onSelectConversation={(conversationId) =>
              void handleSelectConversation(conversationId).catch((caught: Error) => setError(caught.message))
            }
          />
        </div>
      }
      extra={
        streaming ? (
          <Tag color="processing">生成中</Tag>
        ) : pendingConfirmation ? (
          <Tag color="gold">等待确认</Tag>
        ) : (
          <Tag color="green">就绪</Tag>
        )
      }
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
      styles={{ body: { display: "flex", flex: 1, flexDirection: "column", gap: 0, minHeight: 0, overflow: "hidden", padding: 12 } }}
    >
      {!hasModelProfile ? (
        <Alert
          action={
            onOpenModelConfig ? (
              <Button onClick={onOpenModelConfig} size="small" type="primary">
                去配置模型
              </Button>
            ) : undefined
          }
          description="配置模型后可测试连通性，并让 Agent 正常对话、写作和检索。"
          showIcon
          style={{ flexShrink: 0, marginBottom: 10 }}
          title="尚未配置模型"
          type="warning"
        />
      ) : null}
      <div className="agent-panel-chat">
        <ContextStatusBar detail={contextDetail} />
        <div
          className="agent-panel-messages"
          data-testid="agent-message-scroll"
          style={{ flex: "1 1 0", minHeight: 0, overflow: "auto" }}
        >
          <Bubble.List
            autoScroll
            items={messages.map((item) => ({
              key: item.id,
              role: item.role === "assistant" ? "ai" : "user",
              content:
                item.role === "assistant" ? (
                  <AgentMarkdown
                    content={item.content || (streaming && item.id === activeAssistantIdRef.current ? "..." : "")}
                  />
                ) : (
                  item.content
                ),
            }))}
            role={{
              ai: { placement: "start", variant: "shadow" },
              user: { placement: "end", variant: "filled" },
            }}
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
              <Space size={4}>
                <Button size="small" onClick={onUndoWorkspaceDiff}>
                  撤销本次整理
                </Button>
                <Button
                  aria-label="关闭目录变更提示"
                  icon={<CloseOutlined />}
                  onClick={onDismissWorkspaceDiff}
                  size="small"
                  type="text"
                />
              </Space>
            </Flex>
            <Space direction="vertical" size={4} style={{ marginTop: 8, width: "100%" }}>
              {workspaceDiff.changes.map((change) => (
                <Typography.Text key={`${change.action}-${change.node_id}`} type="secondary">
                  {change.action === "move" ? "移动" : change.action === "trash" ? "删除" : change.action}：
                  {change.title}
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
              <Button disabled={streaming} size="small" onClick={() => void handleQuoteAction("analyze")}>
                解析引用
              </Button>
              <Button disabled={streaming} size="small" type="primary" onClick={() => void handleQuoteAction("rewrite")}>
                改写引用
              </Button>
              <Button disabled={streaming} size="small" onClick={() => void handleQuoteAction("polish")}>
                润色引用
              </Button>
            </Space>
          </div>
        ) : null}
        <div className="agent-panel-input" data-testid="agent-input-shell" style={{ flexShrink: 0 }}>
          <Sender
            loading={streaming}
            placeholder="让 Agent 规划、改写、记录记忆或检索上下文"
            value={message}
            onChange={setMessage}
            onSubmit={handleSend}
          />
        </div>
      </div>
      <ContextSettingsDrawer
        novelId={novelId}
        open={settingsOpen}
        token={token}
        onClose={() => setSettingsOpen(false)}
      />
    </Card>
  );
}
