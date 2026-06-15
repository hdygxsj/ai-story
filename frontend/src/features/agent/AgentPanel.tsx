import Bubble from "@ant-design/x/es/bubble";
import Sender from "@ant-design/x/es/sender";
import { CloseOutlined, PushpinOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Flex, Space, Tag, Typography } from "antd";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { AgentConfirmation, AgentStreamDonePayload, AgentToolCallRecord, ContextDetail, WorkspaceDiff } from "../../api/agent";
import { streamAgentMessage } from "../../api/agent";
import type { Conversation } from "../../api/conversations";
import {
  createConversation,
  deleteConversation,
  listConversationMessages,
  listConversations,
  updateConversation,
} from "../../api/conversations";
import type { Novel } from "../../api/novels";
import type { WorkspaceNode } from "../../api/workspace";
import { AgentToolCallCard, DOCUMENT_WRITE_TOOLS, toolLabel } from "./AgentToolTrace";
import { AgentMarkdown } from "./AgentMarkdown";
import { AgentThinkingIndicator } from "./AgentThinkingIndicator";
import {
  type ChatMessage,
  createMessageId,
  expandStoredConversationMessages,
  removeEmptyAssistantMessages,
} from "./agentMessages";
import { ContextSettingsDrawer } from "./ContextSettingsDrawer";
import { ContextStatusBar } from "./ContextStatusBar";
import { ConversationSidebar } from "./ConversationSidebar";
import { getStoredConversationId, setStoredConversationId } from "../workspace/workspaceSessionStorage";
import "./agent-panel.css";

type AgentPanelProps = {
  hasModelProfile?: boolean;
  onOpenModelConfig?: () => void;
  token: string;
  novelId: string;
  documentId?: string | null;
  onClearSelectedText?: () => void;
  onDismissWorkspaceDiff?: () => void;
  onRunCompleted?: (payload: AgentStreamDonePayload) => void | Promise<void>;
  onNovelUpdated?: (novel: Pick<Novel, "id" | "title" | "description">) => void;
  onDocumentWriteLockChange?: (locked: boolean) => void;
  onUndoWorkspaceDiff?: () => void;
  onWorkspaceOrganized?: (nodes: WorkspaceNode[], diff?: WorkspaceDiff | null) => void;
  onWriteConfirmationCreated?: (confirmation: AgentConfirmation) => void;
  rewriteRequest?: { id: number; text: string } | null;
  selectedText?: string | null;
  workspaceDiff?: WorkspaceDiff | null;
};

const WELCOME_MESSAGE = "告诉我你想创建、改写、记录或检索什么。";
const VISIBLE_MESSAGE_LIMIT = 120;

type ThinkingState = {
  startedAt: number;
  content: string;
  phase: "thinking" | "tool";
  toolName?: string;
};

function thinkingLabel(state: ThinkingState): string {
  if (state.phase === "tool" && state.toolName) {
    return `正在执行：${toolLabel(state.toolName)}`;
  }
  return "思考中";
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
  onNovelUpdated,
  onDocumentWriteLockChange,
  onUndoWorkspaceDiff,
  onWorkspaceOrganized,
  onWriteConfirmationCreated,
  rewriteRequest,
  selectedText,
  workspaceDiff,
}: AgentPanelProps) {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(welcomeMessages);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState<ThinkingState | null>(null);
  const [contextDetail, setContextDetail] = useState<ContextDetail | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const activeTextIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesScrollRef = useRef<HTMLDivElement>(null);

  const scrollRafRef = useRef<number | null>(null);

  const scrollMessagesToBottom = useCallback(() => {
    const container = messagesScrollRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, []);

  const scheduleScrollToBottom = useCallback(() => {
    if (scrollRafRef.current !== null) {
      return;
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      scrollMessagesToBottom();
    });
  }, [scrollMessagesToBottom]);

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
      setMessages(expandStoredConversationMessages(stored));
    },
    [novelId, token],
  );

  useEffect(() => {
    setMessage("");
    setError(null);
    setContextDetail(null);

    void (async () => {
      try {
        const items = await refreshConversations();
        const storedConversationId = getStoredConversationId(novelId);
        if (storedConversationId && items.some((item) => item.id === storedConversationId)) {
          setActiveConversationId(storedConversationId);
          await loadConversationMessages(storedConversationId);
          return;
        }
        setActiveConversationId(null);
        setMessages(welcomeMessages());
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();
  }, [loadConversationMessages, novelId, refreshConversations]);

  useEffect(() => {
    if (activeConversationId) {
      setStoredConversationId(novelId, activeConversationId);
    }
  }, [activeConversationId, novelId]);

  useLayoutEffect(() => {
    scheduleScrollToBottom();
    return () => {
      if (scrollRafRef.current !== null) {
        cancelAnimationFrame(scrollRafRef.current);
        scrollRafRef.current = null;
      }
    };
  }, [activeConversationId, messages.length, scheduleScrollToBottom, thinking]);

  function startThinking(content = "") {
    setThinking({ startedAt: Date.now(), content, phase: "thinking" });
  }

  function startToolThinking(toolName: string) {
    setThinking((current) => ({
      startedAt: current?.phase === "tool" ? current.startedAt : Date.now(),
      content: "",
      phase: "tool",
      toolName,
    }));
  }

  function appendThinkingContent(delta: string) {
    setThinking((current) =>
      current
        ? { ...current, content: `${current.content}${delta}`, phase: "thinking", toolName: undefined }
        : { startedAt: Date.now(), content: delta, phase: "thinking" },
    );
  }

  function clearThinking() {
    setThinking(null);
  }

  const documentWriteLocked =
    streaming &&
    messages.some(
      (item) =>
        item.role === "tool" &&
        item.toolCall?.status === "running" &&
        DOCUMENT_WRITE_TOOLS.has(item.toolCall.tool),
    );

  useEffect(() => {
    onDocumentWriteLockChange?.(documentWriteLocked);
  }, [documentWriteLocked, onDocumentWriteLockChange]);

  useEffect(() => {
    return () => {
      onDocumentWriteLockChange?.(false);
    };
  }, [onDocumentWriteLockChange]);

  function ensureActiveTextBubble() {
    if (activeTextIdRef.current) {
      return activeTextIdRef.current;
    }
    const nextId = createMessageId("assistant");
    activeTextIdRef.current = nextId;
    setMessages((current) => [...current, { id: nextId, role: "assistant", content: "" }]);
    return nextId;
  }

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

  function closeActiveTextSegment() {
    const activeId = activeTextIdRef.current;
    if (!activeId) {
      return;
    }
    activeTextIdRef.current = null;
    setMessages((current) => removeEmptyAssistantMessages(current, activeId));
  }

  function upsertToolCallMessage(record: AgentToolCallRecord) {
    if (record.status === "running") {
      closeActiveTextSegment();
      startToolThinking(record.tool);
    } else if (record.status === "ok" || record.status === "error") {
      startThinking();
    }

    setMessages((current) => {
      const existingIndex = current.findIndex(
        (item) => item.role === "tool" && item.toolCall?.id === record.id,
      );
      if (existingIndex === -1) {
        return [
          ...current,
          {
            id: createMessageId("tool"),
            role: "tool",
            content: "",
            toolCall: record,
          },
        ];
      }
      return current.map((item, index) =>
        index === existingIndex ? { ...item, toolCall: record } : item,
      );
    });
  }

  function appendAssistantDelta(delta: string) {
    clearThinking();
    const assistantId = ensureActiveTextBubble();
    appendAssistantContent(assistantId, delta);
  }

  function finalizeActiveTextMessage(content: string) {
    if (activeTextIdRef.current) {
      finalizeAssistantMessage(activeTextIdRef.current, content);
      activeTextIdRef.current = null;
      return;
    }
    if (!content.trim()) {
      return;
    }
    setMessages((current) => [...current, { id: createMessageId("assistant"), role: "assistant", content }]);
  }

  function handleCancelStream() {
    abortControllerRef.current?.abort();
  }

  function finalizeCancelledAssistantMessage() {
    closeActiveTextSegment();
    setMessages((current) => {
      const lastAssistant = [...current].reverse().find((item) => item.role === "assistant");
      if (lastAssistant?.content.trim()) {
        return current;
      }
      if (lastAssistant) {
        return current.map((item) =>
          item.id === lastAssistant.id ? { ...item, content: "（已停止生成）" } : item,
        );
      }
      return [...current, { id: createMessageId("assistant"), role: "assistant", content: "（已停止生成）" }];
    });
  }

  async function sendMessage(value: string, overrideSelectedText?: string | null) {
    if (!value.trim() || streaming) {
      return;
    }
    setError(null);
    setStreaming(true);
    startThinking();

    const controller = new AbortController();
    abortControllerRef.current = controller;
    activeTextIdRef.current = null;

    const placeholderId = createMessageId("assistant");
    activeTextIdRef.current = placeholderId;
    setMessages((current) => [
      ...current.filter((item) => item.content !== WELCOME_MESSAGE || item.role !== "assistant"),
      { id: createMessageId("user"), role: "user", content: value },
      { id: placeholderId, role: "assistant", content: "" },
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
          appendAssistantDelta(content);
        },
        onReasoning: (content) => {
          appendThinkingContent(content);
        },
        onToolCall: (record) => {
          upsertToolCallMessage(record);
        },
        onMeta: (payload) => {
          if (payload.conversation_id) {
            setActiveConversationId(payload.conversation_id);
          }
        },
        onDone: (payload) => {
          if (payload.workspace_nodes) {
            onWorkspaceOrganized?.(payload.workspace_nodes, payload.workspace_diff);
          }
          if (payload.novel_updated) {
            onNovelUpdated?.(payload.novel_updated);
          }
          if (payload.conversation_id) {
            setActiveConversationId(payload.conversation_id);
          }
          setContextDetail(payload.context_detail ?? null);
          if (payload.confirmation) {
            onWriteConfirmationCreated?.(payload.confirmation);
          }
          const finalMessage = payload.confirmation
            ? `${payload.message} 正文写入方案已生成，请在对应章节的编辑器中确认。`
            : payload.message;
          finalizeActiveTextMessage(finalMessage);
          clearThinking();
          void (async () => {
            try {
              await onRunCompleted?.(payload);
            } catch {
              // The completed Agent response remains usable if a background refresh fails.
            }
            setStreaming(false);
            activeTextIdRef.current = null;
            abortControllerRef.current = null;
            void refreshConversations().catch(() => undefined);
          })();
        },
        onError: (caught) => {
          setError(caught.message);
          finalizeActiveTextMessage(caught.message);
          clearThinking();
          setStreaming(false);
          activeTextIdRef.current = null;
          abortControllerRef.current = null;
        },
        onCancelled: () => {
          finalizeCancelledAssistantMessage();
          clearThinking();
          setStreaming(false);
          activeTextIdRef.current = null;
          abortControllerRef.current = null;
          void refreshConversations().catch(() => undefined);
        },
      },
      { signal: controller.signal },
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
        setStoredConversationId(novelId, remaining[0].id);
        await loadConversationMessages(remaining[0].id);
      } else {
        setActiveConversationId(null);
        setStoredConversationId(novelId, null);
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

  const hiddenMessageCount = Math.max(0, messages.length - VISIBLE_MESSAGE_LIMIT);
  const bubbleItems = useMemo(
    () =>
      (hiddenMessageCount > 0 ? messages.slice(-VISIBLE_MESSAGE_LIMIT) : messages)
        .filter(
          (item) =>
            !(
              thinking &&
              item.role === "assistant" &&
              !item.content.trim() &&
              item.id === activeTextIdRef.current
            ),
        )
        .map((item) => ({
          key: item.id,
          role: item.role === "user" ? "user" : "ai",
          content:
            item.role === "tool" && item.toolCall ? (
              <AgentToolCallCard toolCall={item.toolCall} />
            ) : item.role === "assistant" ? (
              <AgentMarkdown content={item.content} />
            ) : (
              item.content
            ),
        })),
    [hiddenMessageCount, messages, thinking],
  );

  return (
    <Card
      className="agent-panel-card"
      title={
        <div className="agent-panel-header">
          <Typography.Title className="agent-panel-header-title" data-testid="agent-panel-header" level={4} style={{ margin: 0 }}>
            执笔
          </Typography.Title>
          <ConversationSidebar
            activeConversationId={activeConversationId}
            conversations={conversations}
            disabled={streaming}
            variant="header"
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
          ref={messagesScrollRef}
          style={{ flex: "1 1 0", minHeight: 0, overflow: "auto" }}
        >
          {hiddenMessageCount > 0 ? (
            <Typography.Text style={{ display: "block", marginBottom: 8 }} type="secondary">
              已折叠较早的 {hiddenMessageCount} 条消息以提升性能
            </Typography.Text>
          ) : null}
          <Bubble.List
            autoScroll
            items={bubbleItems}
            role={{
              ai: { placement: "start", variant: "shadow" },
              user: { placement: "end", variant: "filled" },
            }}
          />
          {thinking ? (
            <AgentThinkingIndicator
              content={thinking.content}
              label={thinkingLabel(thinking)}
              startedAt={thinking.startedAt}
              variant={thinking.phase}
            />
          ) : null}
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
            onCancel={handleCancelStream}
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
