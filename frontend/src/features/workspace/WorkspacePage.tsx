import { Button, Card, Form, Input, List, Select, Space, Statistic, Tabs, Tag, Typography } from "antd";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { AgentPanel } from "../agent/AgentPanel";
import { DocumentEditor } from "../editor/DocumentEditor";
import { WorkspaceTree } from "./WorkspaceTree";
import type { WorkspaceDiff } from "../../api/agent";
import type { Confirmation } from "../../api/confirmations";
import { approveConfirmation, listConfirmations, rejectConfirmation } from "../../api/confirmations";
import type { DocumentBody, DocumentRecord, DocumentVersion } from "../../api/documents";
import { getDocument, listDocumentVersions, updateDocument } from "../../api/documents";
import type { MemoryReviewItem } from "../../api/memory";
import { approveMemoryReviewItem, listMemoryReviewItems, rejectMemoryReviewItem } from "../../api/memory";
import type { CharacterState, CreativeAsset, RelationshipEdge, TimelineEvent } from "../../api/materials";
import {
  listCharacterStates,
  listCreativeAssets,
  listRelationshipEdges,
  listTimelineEvents,
} from "../../api/materials";
import type { ModelProfile } from "../../api/modelProfiles";
import { createModelProfile, listModelProfiles } from "../../api/modelProfiles";
import { updateNovel } from "../../api/novels";
import type { WorkspaceNode } from "../../api/workspace";
import { createWorkspaceNode, listWorkspaceNodes, reorderWorkspaceNodes, updateWorkspaceNode } from "../../api/workspace";

type WorkspacePageProps = {
  activeSection?: WorkspaceSection;
  token: string;
  novelId: string;
};

export type WorkspaceSection = "workspace" | "agent-config" | "memory" | "confirmations" | "materials";

const providerOptions = [
  { label: "OpenAI", value: "openai" },
  { label: "Anthropic", value: "anthropic" },
  { label: "OpenAI 兼容协议", value: "openai-compatible" },
];

const embeddingProviderOptions = [...providerOptions, { label: "Ollama 本地", value: "ollama" }];
const treePanelWidthStorageKey = "ai-story-workspace-tree-width";
const defaultTreePanelWidth = 260;
const minTreePanelWidth = 220;
const maxTreePanelWidth = 480;

function clampTreePanelWidth(width: number) {
  return Math.min(maxTreePanelWidth, Math.max(minTreePanelWidth, Math.round(width)));
}

function initialTreePanelWidth() {
  const stored = Number(window.localStorage.getItem(treePanelWidthStorageKey));
  return Number.isFinite(stored) && stored > 0 ? clampTreePanelWidth(stored) : defaultTreePanelWidth;
}

function providerLabel(value?: string | null): string {
  return providerOptions.find((option) => option.value === value)?.label ?? value ?? "未配置";
}

function extractDocumentText(content: DocumentBody | null): string {
  const parts: string[] = [];

  function visit(node: unknown) {
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    if (!node || typeof node !== "object") {
      return;
    }
    const current = node as { content?: unknown; text?: unknown };
    if (typeof current.text === "string") {
      parts.push(current.text);
    }
    if (current.content) {
      visit(current.content);
    }
  }

  visit(content);
  return parts.join("");
}

export function WorkspacePage({ activeSection = "workspace", token, novelId }: WorkspacePageProps) {
  const [nodes, setNodes] = useState<WorkspaceNode[]>([]);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [draftsByDocumentId, setDraftsByDocumentId] = useState<Record<string, DocumentBody>>({});
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [selectedText, setSelectedText] = useState<string | null>(null);
  const [confirmationCount, setConfirmationCount] = useState(0);
  const [memoryReviewCount, setMemoryReviewCount] = useState(0);
  const [modelProfileCount, setModelProfileCount] = useState(0);
  const [confirmations, setConfirmations] = useState<Confirmation[]>([]);
  const [memoryReviews, setMemoryReviews] = useState<MemoryReviewItem[]>([]);
  const [modelProfiles, setModelProfiles] = useState<ModelProfile[]>([]);
  const [creativeAssets, setCreativeAssets] = useState<CreativeAsset[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [characterStates, setCharacterStates] = useState<CharacterState[]>([]);
  const [relationshipEdges, setRelationshipEdges] = useState<RelationshipEdge[]>([]);
  const [workspaceDiff, setWorkspaceDiff] = useState<WorkspaceDiff | null>(null);
  const [saving, setSaving] = useState(false);
  const [modelProfileSaving, setModelProfileSaving] = useState(false);
  const [modelProfileForm] = Form.useForm();
  const [treePanelWidth, setTreePanelWidth] = useState(initialTreePanelWidth);
  const treeResizeStart = useRef<{ startX: number; startWidth: number } | null>(null);

  function handleEmbeddingProviderChange(providerKind: string) {
    if (providerKind !== "ollama") {
      return;
    }
    modelProfileForm.setFieldsValue({
      embedding_base_url: "http://ollama:11434",
      embedding_model: "nomic-embed-text",
    });
  }

  function handleTreeResizeStart(event: ReactMouseEvent<HTMLDivElement>) {
    treeResizeStart.current = { startWidth: treePanelWidth, startX: event.clientX };
    event.preventDefault();
  }

  useEffect(() => {
    function handleMouseMove(event: MouseEvent) {
      if (!treeResizeStart.current) {
        return;
      }
      const nextWidth = clampTreePanelWidth(
        treeResizeStart.current.startWidth + event.clientX - treeResizeStart.current.startX,
      );
      setTreePanelWidth(nextWidth);
      window.localStorage.setItem(treePanelWidthStorageKey, String(nextWidth));
    }

    function handleMouseUp() {
      treeResizeStart.current = null;
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      try {
        const [
          loadedNodes,
          confirmations,
          memoryReviews,
          modelProfiles,
          assets,
          events,
          states,
          relationships,
        ] = await Promise.all([
          listWorkspaceNodes(token, novelId),
          listConfirmations(token, novelId),
          listMemoryReviewItems(token, novelId),
          listModelProfiles(token),
          listCreativeAssets(token, novelId),
          listTimelineEvents(token, novelId),
          listCharacterStates(token, novelId),
          listRelationshipEdges(token, novelId),
        ]);
        if (!cancelled) {
          setNodes(loadedNodes);
          setDocumentId((current) => {
            if (current && loadedNodes.some((node) => node.document_id === current)) {
              return current;
            }
            return loadedNodes.find((node) => node.document_id)?.document_id ?? null;
          });
          setConfirmations(confirmations);
          setMemoryReviews(memoryReviews);
          setModelProfiles(modelProfiles);
          setCreativeAssets(assets);
          setTimelineEvents(events);
          setCharacterStates(states);
          setRelationshipEdges(relationships);
          setConfirmationCount(confirmations.filter((item) => item.status === "pending").length);
          setMemoryReviewCount(memoryReviews.filter((item) => item.status === "pending").length);
          setModelProfileCount(modelProfiles.length);
        }
      } catch {
        if (!cancelled) {
          setNodes([]);
        }
      }
    }

    void loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, [novelId, token]);

  useEffect(() => {
    if (!documentId) {
      return;
    }

    let cancelled = false;

    async function loadDocument() {
      try {
        const [loadedDocument, loadedVersions] = await Promise.all([
          getDocument(token, documentId as string),
          listDocumentVersions(token, documentId as string),
        ]);
        if (!cancelled) {
          setDocument(loadedDocument);
          setVersions(loadedVersions);
        }
      } catch {
        if (!cancelled) {
          setDocument(null);
          setVersions([]);
        }
      }
    }

    void loadDocument();

    return () => {
      cancelled = true;
    };
  }, [documentId, token]);

  async function handleSaveDocument(content: DocumentBody) {
    if (!documentId) {
      return;
    }
    setSaving(true);
    try {
      const saved = await updateDocument(token, documentId, content);
      const loadedVersions = await listDocumentVersions(token, documentId);
      setDocument(saved);
      setVersions(loadedVersions);
      setDraftsByDocumentId((current) => {
        const next = { ...current };
        delete next[documentId];
        return next;
      });
    } finally {
      setSaving(false);
    }
  }

  function handleDocumentDraftChange(content: DocumentBody) {
    if (!documentId) {
      return;
    }
    setDraftsByDocumentId((current) => ({ ...current, [documentId]: content }));
  }

  async function refreshReviewQueues() {
    const [loadedConfirmations, loadedMemoryReviews] = await Promise.all([
      listConfirmations(token, novelId),
      listMemoryReviewItems(token, novelId),
    ]);
    setConfirmations(loadedConfirmations);
    setMemoryReviews(loadedMemoryReviews);
    setConfirmationCount(loadedConfirmations.filter((item) => item.status === "pending").length);
    setMemoryReviewCount(loadedMemoryReviews.filter((item) => item.status === "pending").length);
  }

  async function resolveConfirmation(confirmationId: string, action: "approve" | "reject") {
    if (action === "approve") {
      await approveConfirmation(token, confirmationId);
    } else {
      await rejectConfirmation(token, confirmationId);
    }
    await refreshReviewQueues();
    if (documentId) {
      setDocument(await getDocument(token, documentId));
    }
  }

  async function resolveMemoryReview(itemId: string, action: "approve" | "reject") {
    if (action === "approve") {
      await approveMemoryReviewItem(token, itemId);
    } else {
      await rejectMemoryReviewItem(token, itemId);
    }
    await refreshReviewQueues();
  }

  function handleSelectDocument(nextDocumentId: string) {
    setDocumentId(nextDocumentId);
  }

  async function handleCreateModelProfile(values: {
    api_key: string;
    base_url?: string;
    chat_api_key?: string;
    chat_base_url?: string;
    chat_model: string;
    chat_provider_kind?: string;
    embedding_api_key?: string;
    embedding_base_url?: string;
    embedding_model: string;
    embedding_provider_kind?: string;
    name: string;
    provider_kind: string;
    summary_api_key?: string;
    summary_base_url?: string;
    summary_model: string;
    summary_provider_kind?: string;
    writing_api_key?: string;
    writing_base_url?: string;
    writing_model: string;
    writing_provider_kind?: string;
  }) {
    setModelProfileSaving(true);
    try {
      const profile = await createModelProfile(token, {
        ...values,
        base_url: values.base_url || null,
        chat_api_key: values.chat_api_key || null,
        chat_base_url: values.chat_base_url || null,
        chat_provider_kind: values.chat_provider_kind || null,
        context_window: 128000,
        embedding_api_key: values.embedding_api_key || null,
        embedding_base_url: values.embedding_base_url || null,
        embedding_dimensions: 1536,
        embedding_provider_kind: values.embedding_provider_kind || null,
        summary_api_key: values.summary_api_key || null,
        summary_base_url: values.summary_base_url || null,
        summary_provider_kind: values.summary_provider_kind || null,
        supports_json_mode: true,
        supports_streaming: true,
        supports_tool_calling: true,
        writing_api_key: values.writing_api_key || null,
        writing_base_url: values.writing_base_url || null,
        writing_provider_kind: values.writing_provider_kind || null,
      });
      setModelProfiles((current) => [...current, profile]);
      setModelProfileCount((current) => current + 1);
      await updateNovel(token, novelId, { default_model_profile_id: profile.id });
      modelProfileForm.resetFields();
    } finally {
      setModelProfileSaving(false);
    }
  }

  async function handleCreateWorkspaceNode(nodeType: "chapter" | "folder", parentId: string | null = null) {
    const title = nodeType === "chapter" ? "新章节" : "新文件夹";
    const node = await createWorkspaceNode(token, novelId, title, nodeType, parentId);
    setNodes((current) => [...current, node]);
    if (node.document_id) {
      setDocumentId(node.document_id);
    }
  }

  async function handleUpdateWorkspaceNode(nodeId: string, payload: Partial<Pick<WorkspaceNode, "parent_id" | "position" | "title">>) {
    const node = await updateWorkspaceNode(token, novelId, nodeId, payload);
    setNodes((current) => current.map((item) => (item.id === node.id ? node : item)));
  }

  async function handleReorderWorkspaceNodes(items: Array<Pick<WorkspaceNode, "id" | "parent_id" | "position">>) {
    const reorderedNodes = await reorderWorkspaceNodes(token, novelId, items);
    setNodes(reorderedNodes);
  }

  function collectNodeAndDescendants(nodeId: string) {
    const collected = new Set<string>([nodeId]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const node of nodes) {
        if (node.parent_id && collected.has(node.parent_id) && !collected.has(node.id)) {
          collected.add(node.id);
          changed = true;
        }
      }
    }
    return nodes.filter((node) => collected.has(node.id));
  }

  async function handleWorkspaceNodeStatus(nodeId: string, status: string) {
    const targetNodes = collectNodeAndDescendants(nodeId);
    const updatedNodes = await reorderWorkspaceNodes(
      token,
      novelId,
      targetNodes.map((node) => ({
        id: node.id,
        parent_id: node.parent_id,
        position: node.position,
        status,
      })),
    );
    setNodes(updatedNodes);
    if (status === "trashed" && currentChapterNode && targetNodes.some((node) => node.id === currentChapterNode.id)) {
      const nextDocumentId = updatedNodes.find((node) => node.status !== "trashed" && node.document_id)?.document_id ?? null;
      setDocumentId(nextDocumentId);
    }
  }

  async function handleUndoWorkspaceDiff() {
    if (!workspaceDiff) {
      return;
    }
    const restoredNodes = await reorderWorkspaceNodes(
      token,
      novelId,
      workspaceDiff.before.map((node) => ({
        id: node.id,
        parent_id: node.parent_id,
        position: node.position,
        status: node.status,
        title: node.title,
      })),
    );
    setNodes(restoredNodes);
    setWorkspaceDiff(null);
  }

  const serverDocumentContent = document?.id === documentId ? document.content : null;
  const editorContent = documentId ? draftsByDocumentId[documentId] ?? serverDocumentContent : null;
  const hasUnsavedDraft = Boolean(documentId && draftsByDocumentId[documentId]);
  const activeNodes = nodes.filter((node) => node.status !== "trashed");
  const chapterCount = activeNodes.filter((node) => node.node_type !== "folder").length;
  const folderCount = activeNodes.filter((node) => node.node_type === "folder").length;
  const currentWordCount = extractDocumentText(editorContent).length;
  const currentChapterNode = nodes.find((node) => node.document_id === documentId) ?? null;
  const currentChapterTitle = currentChapterNode?.title ?? null;

  const workspaceStats = (
    <Card
      size="small"
      style={{
        background: "linear-gradient(135deg, rgba(255,122,24,0.12), rgba(255,255,255,0.86))",
        border: "1px solid rgba(255,122,24,0.16)",
        borderRadius: 18,
        boxShadow: "0 12px 34px rgba(255,122,24,0.08)",
      }}
    >
      <div style={{ alignItems: "center", display: "grid", gap: 14, gridTemplateColumns: "1.2fr repeat(4, minmax(90px, 1fr))" }}>
        <div>
          <Typography.Text strong>作品概览</Typography.Text>
          <Typography.Text style={{ color: "#f97316", display: "block", fontSize: 12 }}>今日也要稳定更新</Typography.Text>
        </div>
        <Statistic title="章节" value={chapterCount} styles={{ content: { color: "#111827", fontSize: 20 } }} />
        <Statistic title="文件夹" value={folderCount} styles={{ content: { color: "#111827", fontSize: 20 } }} />
        <Statistic title="当前字数" value={currentWordCount} styles={{ content: { color: "#111827", fontSize: 20 } }} />
        <Tag color={hasUnsavedDraft ? "orange" : "green"} style={{ justifySelf: "end", marginInlineEnd: 0 }}>
          {hasUnsavedDraft ? "有本地草稿" : "已同步"}
        </Tag>
      </div>
    </Card>
  );

  const chapterTreePanel = (
    <WorkspaceTree
      nodes={nodes}
      onCreateChapter={(parentId) => void handleCreateWorkspaceNode("chapter", parentId ?? null)}
      onCreateFolder={(parentId) => void handleCreateWorkspaceNode("folder", parentId ?? null)}
      onMoveNode={(nodeId, parentId, position) =>
        void handleUpdateWorkspaceNode(nodeId, { parent_id: parentId, position })
      }
      onReorderNodes={(changes) => void handleReorderWorkspaceNodes(changes)}
      onRenameNode={(nodeId, title) => void handleUpdateWorkspaceNode(nodeId, { title })}
      onRestoreNode={(nodeId) => void handleWorkspaceNodeStatus(nodeId, "draft")}
      onSelectDocument={handleSelectDocument}
      onTrashNode={(nodeId) => void handleWorkspaceNodeStatus(nodeId, "trashed")}
    />
  );

  const agentPanel = (
    <AgentPanel
      token={token}
      novelId={novelId}
      documentId={documentId}
      onClearSelectedText={() => setSelectedText(null)}
      onUndoWorkspaceDiff={() => void handleUndoWorkspaceDiff()}
      onWorkspaceOrganized={(updatedNodes, diff) => {
        setNodes(updatedNodes);
        setWorkspaceDiff(diff);
      }}
      selectedText={selectedText}
      workspaceDiff={workspaceDiff}
    />
  );

  function renderWorkspaceShell(centerContent: ReactNode) {
    return (
      <div
        data-testid="workspace-shell"
        style={{
          display: "grid",
          gap: 12,
          gridTemplateRows: "auto minmax(0, 1fr)",
          height: "100%",
          minHeight: 0,
          minWidth: 0,
        }}
      >
        {workspaceStats}
        <div
          data-testid="workspace-grid"
          style={{
            display: "grid",
            gap: 14,
            gridTemplateColumns: `${treePanelWidth}px 6px minmax(0, 1fr) clamp(300px, 28vw, 390px)`,
            minHeight: 0,
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {chapterTreePanel}
          <div
            aria-label="调整章节面板宽度"
            role="separator"
            aria-orientation="vertical"
            onMouseDown={handleTreeResizeStart}
            style={{
              alignSelf: "stretch",
              cursor: "col-resize",
              marginInline: -4,
              position: "relative",
              zIndex: 2,
            }}
          >
            <div
              style={{
                background: "rgba(15,23,42,0.08)",
                borderRadius: 999,
                height: "100%",
                margin: "0 auto",
                width: 2,
              }}
            />
          </div>
          {centerContent}
          {agentPanel}
        </div>
      </div>
    );
  }

  const workspaceContent = renderWorkspaceShell(
    <DocumentEditor
      chapterTitle={currentChapterTitle}
      content={editorContent}
      onChange={handleDocumentDraftChange}
      onRenameChapter={(title) => {
        if (currentChapterNode) {
          void handleUpdateWorkspaceNode(currentChapterNode.id, { title });
        }
      }}
      onSave={handleSaveDocument}
      onSelectText={setSelectedText}
      saveStatus={saving ? "saving" : hasUnsavedDraft ? "dirty" : "saved"}
      saving={saving}
    />,
  );

  const agentConfigContent = (
    <Card
      data-testid="agent-config-card"
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15,23,42,0.08)",
        margin: "0 auto",
        maxWidth: 960,
        width: "100%",
      }}
    >
      <Typography.Title level={3}>Agent配置</Typography.Title>
      <Typography.Paragraph type="secondary">
        配置 OpenAI、Anthropic 或兼容 OpenAI 协议的模型供应商，供 Agent 对话、写作、总结和向量检索使用。
      </Typography.Paragraph>
      <Form
        form={modelProfileForm}
        initialValues={{
          chat_model: "gpt-4o",
          chat_api_key: "",
          chat_provider_kind: "openai",
          embedding_model: "text-embedding-3-small",
          embedding_api_key: "",
          embedding_provider_kind: "openai",
          name: "默认 OpenAI",
          provider_kind: "openai",
          summary_model: "gpt-4o-mini",
          summary_api_key: "",
          summary_provider_kind: "openai",
          writing_model: "gpt-4o",
          writing_api_key: "",
          writing_provider_kind: "openai",
        }}
        layout="vertical"
        onFinish={handleCreateModelProfile}
        style={{ maxWidth: 720 }}
      >
        <Form.Item label="配置名称" name="name" rules={[{ required: true, message: "请输入配置名称" }]}>
          <Input />
        </Form.Item>
        <Form.Item label="供应商" name="provider_kind" rules={[{ required: true, message: "请选择供应商" }]}>
          <Select options={providerOptions} />
        </Form.Item>
        <Tabs
          destroyOnHidden={false}
          items={[
            {
              key: "default",
              label: "默认",
              children: (
                <>
                  <Typography.Paragraph type="secondary">
                    默认配置作为所有模型的回退。某个模型 Tab 不填 API Key 或 Base URL 时，会使用这里的值。
                  </Typography.Paragraph>
                  <Form.Item label="默认 Base URL（可选）" name="base_url">
                    <Input placeholder="https://api.openai.com/v1" />
                  </Form.Item>
                  <Form.Item label="默认 API Key" name="api_key" rules={[{ required: true, message: "请输入默认 API Key" }]}>
                    <Input.Password />
                  </Form.Item>
                </>
              ),
            },
            {
              key: "chat",
              label: "对话",
              children: (
                <>
                  <Form.Item label="对话场景供应商" name="chat_provider_kind">
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label="对话模型" name="chat_model" rules={[{ required: true, message: "请输入对话模型" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="对话 Base URL" name="chat_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="对话 API Key" name="chat_api_key">
                    <Input.Password placeholder="不填则使用默认 API Key" />
                  </Form.Item>
                </>
              ),
            },
            {
              key: "writing",
              label: "写作",
              children: (
                <>
                  <Form.Item label="写作场景供应商" name="writing_provider_kind">
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label="写作模型" name="writing_model" rules={[{ required: true, message: "请输入写作模型" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="写作 Base URL" name="writing_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="写作 API Key" name="writing_api_key">
                    <Input.Password placeholder="不填则使用默认 API Key" />
                  </Form.Item>
                </>
              ),
            },
            {
              key: "summary",
              label: "总结",
              children: (
                <>
                  <Form.Item label="总结场景供应商" name="summary_provider_kind">
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label="总结模型" name="summary_model" rules={[{ required: true, message: "请输入总结模型" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="总结 Base URL" name="summary_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="总结 API Key" name="summary_api_key">
                    <Input.Password placeholder="不填则使用默认 API Key" />
                  </Form.Item>
                </>
              ),
            },
            {
              key: "embedding",
              label: "向量",
              children: (
                <>
                  <Form.Item label="向量场景供应商" name="embedding_provider_kind">
                    <Select onChange={handleEmbeddingProviderChange} options={embeddingProviderOptions} />
                  </Form.Item>
                  <Form.Item label="向量模型" name="embedding_model" rules={[{ required: true, message: "请输入向量模型" }]}>
                    <Input />
                  </Form.Item>
                  <Form.Item label="向量 Base URL" name="embedding_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="向量 API Key" name="embedding_api_key">
                    <Input.Password placeholder="不填则使用默认 API Key" />
                  </Form.Item>
                </>
              ),
            },
          ]}
        />
        <Button htmlType="submit" loading={modelProfileSaving} type="primary">
          保存 Agent 配置
        </Button>
      </Form>
      <List
        dataSource={modelProfiles}
        header={<strong>已配置模型</strong>}
        locale={{ emptyText: "还没有模型配置" }}
        renderItem={(profile) => {
          const fallbackProvider = profile.provider_kind;
          return (
            <List.Item>
              <List.Item.Meta
                description={
                  <Space size={[8, 8]} wrap>
                    <Tag color="blue">对话 {providerLabel(profile.chat_provider_kind ?? fallbackProvider)} · {profile.chat_model}</Tag>
                    <Tag color="green">写作 {providerLabel(profile.writing_provider_kind ?? fallbackProvider)} · {profile.writing_model}</Tag>
                    <Tag color="purple">总结 {providerLabel(profile.summary_provider_kind ?? fallbackProvider)} · {profile.summary_model}</Tag>
                    <Tag color="orange">向量 {providerLabel(profile.embedding_provider_kind ?? fallbackProvider)} · {profile.embedding_model}</Tag>
                  </Space>
                }
                title={profile.name}
              />
            </List.Item>
          );
        }}
        style={{ marginTop: 24 }}
      />
    </Card>
  );

  const memoryContent = renderWorkspaceShell(
    <Card
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15,23,42,0.08)",
        height: "100%",
        minWidth: 0,
      }}
      styles={{ body: { height: "100%", overflow: "auto" } }}
    >
      <Typography.Title level={3}>记忆</Typography.Title>
      <Typography.Paragraph>在这里审核关键记忆、角色状态、时间线事件和 RAG 上下文。</Typography.Paragraph>
      <Tag color="blue">{memoryReviewCount} 条待审核</Tag>
      <Tag>{modelProfileCount} 个模型配置</Tag>
      <List
        dataSource={memoryReviews}
        locale={{ emptyText: "没有待审核记忆" }}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button size="small" onClick={() => void resolveMemoryReview(item.id, "approve")}>
                通过
              </Button>,
              <Button danger size="small" onClick={() => void resolveMemoryReview(item.id, "reject")}>
                拒绝
              </Button>,
            ]}
          >
            <List.Item.Meta description={`${item.memory_type} · importance ${item.importance}`} title={item.title} />
          </List.Item>
        )}
        style={{ marginTop: 16 }}
      />
      <List
        dataSource={modelProfiles}
        locale={{ emptyText: "还没有模型配置" }}
        renderItem={(profile) => (
          <List.Item>
            <List.Item.Meta description={`${profile.provider_kind} · ${profile.chat_model}`} title={profile.name} />
          </List.Item>
        )}
        style={{ marginTop: 16 }}
      />
    </Card>
  );

  const confirmationsContent = (
    <Card style={{ border: "none", boxShadow: "0 18px 45px rgba(15,23,42,0.08)" }}>
      <Typography.Title level={3}>确认</Typography.Title>
      <Typography.Paragraph>Agent 的写入动作会先进入这里，等待你通过或拒绝。</Typography.Paragraph>
      <Space wrap>
        <Tag color="gold">{confirmationCount} 条待确认</Tag>
        <Tag>{versions.length} 个已保存版本</Tag>
      </Space>
      <List
        dataSource={confirmations}
        locale={{ emptyText: "没有待确认操作" }}
        renderItem={(confirmation) => (
          <List.Item
            actions={[
              <Button size="small" onClick={() => void resolveConfirmation(confirmation.id, "approve")}>
                通过
              </Button>,
              <Button danger size="small" onClick={() => void resolveConfirmation(confirmation.id, "reject")}>
                拒绝
              </Button>,
            ]}
          >
            <List.Item.Meta
              description={String(confirmation.payload.replacement_text ?? "")}
              title={confirmation.action_type}
            />
          </List.Item>
        )}
        style={{ marginTop: 16 }}
      />
    </Card>
  );

  const materialsContent = renderWorkspaceShell(
    <Card
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15,23,42,0.08)",
        height: "100%",
        minWidth: 0,
      }}
      styles={{ body: { height: "100%", overflow: "auto" } }}
    >
      <Typography.Title level={3}>素材</Typography.Title>
      <Typography.Paragraph>管理结构化创作素材、时间线、角色状态和人物关系。</Typography.Paragraph>
      <List
        dataSource={creativeAssets}
        header={<strong>创作资产</strong>}
        renderItem={(asset) => (
          <List.Item>
            <List.Item.Meta description={`${asset.asset_type} · ${asset.summary}`} title={asset.name} />
          </List.Item>
        )}
      />
      <List
        dataSource={timelineEvents}
        header={<strong>时间线</strong>}
        renderItem={(event) => (
          <List.Item>
            <List.Item.Meta description={event.event_time} title={event.title} />
          </List.Item>
        )}
      />
      <List
        dataSource={characterStates}
        header={<strong>角色状态</strong>}
        renderItem={(state) => (
          <List.Item>
            <List.Item.Meta description={state.character_name} title={state.state} />
          </List.Item>
        )}
      />
      <List
        dataSource={relationshipEdges}
        header={<strong>人物关系</strong>}
        renderItem={(edge) => (
          <List.Item>
            <List.Item.Meta description={`${edge.source_character} -> ${edge.target_character}`} title={edge.relationship_type} />
          </List.Item>
        )}
      />
    </Card>
  );

  const sectionContent: Record<WorkspaceSection, ReactNode> = {
    "agent-config": agentConfigContent,
    confirmations: confirmationsContent,
    materials: materialsContent,
    memory: memoryContent,
    workspace: workspaceContent,
  };

  return <div style={{ height: "100%", minHeight: 0, minWidth: 0 }}>{sectionContent[activeSection]}</div>;
}
