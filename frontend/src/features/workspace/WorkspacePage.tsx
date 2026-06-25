import { RightOutlined, SearchOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Flex, Form, Input, List, message, Popconfirm, Select, Space, Statistic, Tabs, Tag, Timeline, Typography } from "antd";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { documentBodiesEqual, extractDocumentBodyText } from "../editor/documentBodyText";
import { debounce } from "../../utils/schedule";
import { AgentPanel } from "../agent/AgentPanel";
import { MATERIAL_REFRESH_TOOLS } from "../agent/AgentToolTrace";
import { DocumentEditor } from "../editor/DocumentEditor";
import { DocumentVersionHistory } from "../editor/DocumentVersionHistory";
import { MaterialsPanel } from "./MaterialsPanel";
import { NovelSearchModal } from "./NovelSearchModal";
import { prepareTimelineEvents } from "./timelinePresentation";
import { WorkspaceTree } from "./WorkspaceTree";
import { ApiError } from "../../api/http";
import type { AgentStreamDonePayload, WorkspaceDiff } from "../../api/agent";
import { runAgentTool } from "../../api/agent";
import type { Confirmation } from "../../api/confirmations";
import { approveConfirmation, listConfirmations, rejectConfirmation } from "../../api/confirmations";
import { ConfirmationsPanel } from "../confirmations/ConfirmationsPanel";
import { loadConfirmationHistorySafe } from "../confirmations/loadConfirmationHistorySafe";
import {
  pendingDocumentWriteConfirmations,
  pendingDocumentWriteCountsByDocumentId,
} from "../confirmations/confirmationPresentation";
import type { DocumentBody, DocumentRecord, DocumentVersion } from "../../api/documents";
import { getDocument, listDocumentVersions, restoreDocumentVersion, updateDocument } from "../../api/documents";
import type { MemoryItem } from "../../api/memory";
import { deleteMemoryItem, listMemoryItems } from "../../api/memory";
import type {
  CharacterAttribute,
  CharacterAttributePayload,
  CharacterState,
  CreativeAsset,
  InventoryItem,
  InventoryItemPayload,
  MapLocation,
  MapLocationPayload,
  MaterialChange,
  RelationshipEdge,
  TimelineEvent,
} from "../../api/materials";
import {
  deleteCharacterAttribute,
  deleteCreativeAsset,
  deleteInventoryItem,
  deleteMapLocation,
  listCharacterAttributes,
  listCharacterStates,
  listCreativeAssets,
  listInventoryItems,
  listMapLocations,
  listMaterialChanges,
  listRelationshipEdges,
  listTimelineEvents,
  updateCharacterAttribute,
  updateCreativeAsset,
  updateInventoryItem,
  updateMapLocation,
  upsertCharacterAttribute,
  upsertInventoryItem,
  upsertMapLocation,
} from "../../api/materials";
import type { ModelProfile } from "../../api/modelProfiles";
import type { ModelProfileConnectivityResult, ModelProfilePurpose } from "../../api/modelProfiles";
import {
  createModelProfile,
  deleteModelProfile,
  listModelProfiles,
  testModelProfileConnectivity,
  updateModelProfile,
} from "../../api/modelProfiles";
import { updateNovel } from "../../api/novels";
import type { DocumentSearchHit } from "../../api/search";
import { ollamaDefaults } from "../../config/ollama";
import type { WorkspaceNode } from "../../api/workspace";
import {
  createWorkspaceNode,
  emptyWorkspaceTrash,
  exportWorkspaceNode,
  listWorkspaceNodes,
  reorderWorkspaceNodes,
  updateWorkspaceNode,
} from "../../api/workspace";
import { getStoredDocumentId, setStoredDocumentId } from "./workspaceSessionStorage";

type WorkspacePageProps = {
  activeSection?: WorkspaceSection;
  defaultModelProfileId?: string | null;
  onActiveSectionChange?: (section: WorkspaceSection) => void;
  onDefaultModelProfileChange?: (profileId: string | null) => void;
  onNovelUpdated?: (novel: Pick<import("../../api/novels").Novel, "id" | "title" | "description">) => void;
  onOpenAgentConfig?: () => void;
  onPendingConfirmationCountChange?: (count: number) => void;
  token: string;
  novelId: string;
};

export type WorkspaceSection = "workspace" | "agent-config" | "memory" | "confirmations" | "materials" | "timeline" | "scoring";

type ChapterScoreDetail = {
  hook: number;
  progress: number;
  character: number;
  conflict: number;
  language_originality: number;
};

type ChapterScore = {
  node_id: string;
  chapter_title: string;
  total_score: number;
  platform_risk: string;
  details: ChapterScoreDetail;
  reasons: string[];
  suggestions: string[];
};

type ChapterScoreResult = {
  status: string;
  scores: ChapterScore[];
  summary: {
    average_score: number;
    chapter_count: number;
  };
  rubric: {
    total_points: number;
  };
};

const providerOptions = [
  { label: "OpenAI", value: "openai" },
  { label: "Anthropic", value: "anthropic" },
  { label: "OpenAI 兼容协议", value: "openai-compatible" },
];

const embeddingProviderOptions = [
  { label: "Ollama 本地", value: "ollama" },
  { label: "OpenAI 兼容协议", value: "openai-compatible" },
];

type ModelConfigTab = "default" | "chat" | "writing" | "summary" | "embedding";

const MODEL_TAB_PURPOSES: Record<ModelConfigTab, ModelProfilePurpose[]> = {
  chat: ["chat"],
  default: ["chat", "writing", "summary"],
  embedding: ["embedding"],
  summary: ["summary"],
  writing: ["writing"],
};

function modelTabValidateFields(tab: ModelConfigTab, editing: boolean): string[] {
  const shared = editing ? ["name", "provider_kind"] : ["name", "provider_kind", "api_key"];
  switch (tab) {
    case "default":
      return [...shared, "base_url", "chat_model", "writing_model", "summary_model"];
    case "chat":
      return [...shared, "chat_provider_kind", "chat_model", "chat_base_url", "chat_api_key"];
    case "writing":
      return [...shared, "writing_provider_kind", "writing_model", "writing_base_url", "writing_api_key"];
    case "summary":
      return [...shared, "summary_provider_kind", "summary_model", "summary_base_url", "summary_api_key"];
    case "embedding":
      return [
        ...shared,
        "embedding_provider_kind",
        "embedding_model",
        "embedding_base_url",
        "embedding_api_key",
      ];
  }
}

const defaultModelProfileFormValues = {
  chat_model: "gpt-4o",
  chat_provider_kind: "openai",
  name: "默认 OpenAI",
  provider_kind: "openai",
  summary_model: "gpt-4o-mini",
  summary_provider_kind: "openai",
  writing_model: "gpt-4o",
  writing_provider_kind: "openai",
};

function profileToFormValues(profile: ModelProfile) {
  return {
    base_url: profile.base_url ?? undefined,
    chat_base_url: profile.chat_base_url ?? undefined,
    chat_model: profile.chat_model,
    chat_provider_kind: profile.chat_provider_kind ?? undefined,
    embedding_base_url:
      profile.embedding_base_url ??
      (profile.embedding_provider_kind === "ollama" ? ollamaDefaults.baseUrl : undefined),
    embedding_model: profile.embedding_model?.trim()
      ? profile.embedding_model
      : profile.embedding_provider_kind === "ollama"
        ? ollamaDefaults.embeddingModel
        : undefined,
    embedding_provider_kind:
      profile.embedding_provider_kind ??
      (profile.embedding_base_url?.includes("11434") || profile.embedding_model === ollamaDefaults.embeddingModel
        ? "ollama"
        : undefined),
    name: profile.name,
    provider_kind: profile.provider_kind,
    summary_base_url: profile.summary_base_url ?? undefined,
    summary_model: profile.summary_model,
    summary_provider_kind: profile.summary_provider_kind ?? undefined,
    writing_base_url: profile.writing_base_url ?? undefined,
    writing_model: profile.writing_model,
    writing_provider_kind: profile.writing_provider_kind ?? undefined,
  };
}
const treePanelWidthStorageKey = "ai-story-workspace-tree-width";
const treePanelCollapsedStorageKey = "ai-story-workspace-tree-collapsed";
const agentPanelWidthStorageKey = "ai-story-agent-panel-width";
const defaultTreePanelWidth = 260;
const defaultAgentPanelWidth = 420;
const minTreePanelWidth = 220;
const maxTreePanelWidth = 480;
const minAgentPanelWidth = 320;
const maxAgentPanelWidth = 640;

function clampTreePanelWidth(width: number) {
  return Math.min(maxTreePanelWidth, Math.max(minTreePanelWidth, Math.round(width)));
}

function initialTreePanelWidth() {
  const stored = Number(window.localStorage.getItem(treePanelWidthStorageKey));
  return Number.isFinite(stored) && stored > 0 ? clampTreePanelWidth(stored) : defaultTreePanelWidth;
}

function clampAgentPanelWidth(width: number) {
  return Math.min(maxAgentPanelWidth, Math.max(minAgentPanelWidth, Math.round(width)));
}

function initialAgentPanelWidth() {
  const stored = Number(window.localStorage.getItem(agentPanelWidthStorageKey));
  return Number.isFinite(stored) && stored > 0 ? clampAgentPanelWidth(stored) : defaultAgentPanelWidth;
}

function initialTreePanelCollapsed() {
  return window.localStorage.getItem(treePanelCollapsedStorageKey) === "true";
}

function providerLabel(value?: string | null): string {
  return providerOptions.find((option) => option.value === value)?.label ?? value ?? "未配置";
}

function embeddingProviderLabel(value?: string | null): string {
  return embeddingProviderOptions.find((option) => option.value === value)?.label ?? value ?? "未配置";
}

function normalizeEmbeddingConfig<T extends {
  embedding_base_url?: string;
  embedding_model?: string;
  embedding_provider_kind?: string;
}>(values: T): T {
  const embeddingModel = values.embedding_model?.trim() || "";
  if (!embeddingModel) {
    return { ...values, embedding_model: "", embedding_provider_kind: undefined, embedding_base_url: undefined };
  }
  let embeddingProviderKind = values.embedding_provider_kind;
  let embeddingBaseUrl = values.embedding_base_url;
  if (
    !embeddingProviderKind &&
    (embeddingBaseUrl?.includes("11434") || embeddingModel === ollamaDefaults.embeddingModel)
  ) {
    embeddingProviderKind = "ollama";
  }
  if (embeddingProviderKind === "ollama") {
    embeddingBaseUrl = embeddingBaseUrl || ollamaDefaults.baseUrl;
  }
  return {
    ...values,
    embedding_base_url: embeddingBaseUrl,
    embedding_model: embeddingModel,
    embedding_provider_kind: embeddingProviderKind,
  };
}

const optionalPurposeFields = [
  "base_url",
  "chat_api_key",
  "chat_base_url",
  "chat_provider_kind",
  "embedding_api_key",
  "embedding_base_url",
  "embedding_provider_kind",
  "summary_api_key",
  "summary_base_url",
  "summary_provider_kind",
  "writing_api_key",
  "writing_base_url",
  "writing_provider_kind",
] as const;

function createDirtyDraftTracker() {
  const drafts: Record<string, DocumentBody> = {};
  const dirtyIds = new Set<string>();
  let revision = 0;

  return {
    getDraft(documentId: string) {
      return drafts[documentId];
    },
    updateDraft(
      documentId: string,
      content: DocumentBody,
      serverContent: DocumentBody | null | undefined,
    ) {
      const wasDirty = dirtyIds.has(documentId);
      if (!wasDirty) {
        if (serverContent && documentBodiesEqual(content, serverContent)) {
          return { dirtyChanged: false, revision };
        }
        drafts[documentId] = content;
        dirtyIds.add(documentId);
        revision += 1;
        return { dirtyChanged: true, revision };
      }
      drafts[documentId] = content;
      return { dirtyChanged: false, revision };
    },
    clearDraft(documentId: string) {
      delete drafts[documentId];
      if (dirtyIds.delete(documentId)) {
        revision += 1;
      }
      return revision;
    },
    isDirty(documentId: string | null) {
      return Boolean(documentId && dirtyIds.has(documentId));
    },
    getRevision() {
      return revision;
    },
  };
}

export function WorkspacePage({
  activeSection = "workspace",
  defaultModelProfileId = null,
  onActiveSectionChange,
  onDefaultModelProfileChange,
  onNovelUpdated,
  onOpenAgentConfig,
  onPendingConfirmationCountChange,
  token,
  novelId,
}: WorkspacePageProps) {
  const [nodes, setNodes] = useState<WorkspaceNode[]>([]);
  const [documentId, setDocumentId] = useState<string | null>(() => getStoredDocumentId(novelId));
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [documentLoading, setDocumentLoading] = useState(() => getStoredDocumentId(novelId) != null);
  const [scoringScope, setScoringScope] = useState<"all" | "current" | "selected">("all");
  const [selectedScoringNodeIds, setSelectedScoringNodeIds] = useState<string[]>([]);
  const [chapterScoreResult, setChapterScoreResult] = useState<ChapterScoreResult | null>(null);
  const [chapterScoring, setChapterScoring] = useState(false);
  const [agentDocumentWriteLocked, setAgentDocumentWriteLocked] = useState(false);
  const draftTrackerRef = useRef(createDirtyDraftTracker());
  const [draftRevision, setDraftRevision] = useState(0);
  const [currentWordCount, setCurrentWordCount] = useState(0);
  const scheduleWordCountUpdateRef = useRef(
    debounce((content: DocumentBody) => {
      setCurrentWordCount(extractDocumentBodyText(content).length);
    }, 400),
  );
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [selectedText, setSelectedText] = useState<string | null>(null);
  const [confirmationCount, setConfirmationCount] = useState(0);
  const [modelProfileCount, setModelProfileCount] = useState(0);
  const [confirmations, setConfirmations] = useState<Confirmation[]>([]);
  const [confirmationHistory, setConfirmationHistory] = useState<Confirmation[]>([]);
  const [focusConfirmationId, setFocusConfirmationId] = useState<string | null>(null);
  const [focusSearchRange, setFocusSearchRange] = useState<{ matchIndex: number; matchLength: number } | null>(null);
  const [novelSearchOpen, setNovelSearchOpen] = useState(false);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [modelProfiles, setModelProfiles] = useState<ModelProfile[]>([]);
  const [creativeAssets, setCreativeAssets] = useState<CreativeAsset[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [characterStates, setCharacterStates] = useState<CharacterState[]>([]);
  const [characterAttributes, setCharacterAttributes] = useState<CharacterAttribute[]>([]);
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [mapLocations, setMapLocations] = useState<MapLocation[]>([]);
  const [relationshipEdges, setRelationshipEdges] = useState<RelationshipEdge[]>([]);
  const [materialChanges, setMaterialChanges] = useState<MaterialChange[]>([]);
  const [workspaceDiff, setWorkspaceDiff] = useState<WorkspaceDiff | null>(null);
  const [saving, setSaving] = useState(false);
  const [versionHistoryOpen, setVersionHistoryOpen] = useState(false);
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null);
  const [modelProfileSaving, setModelProfileSaving] = useState(false);
  const [connectivityTestingTab, setConnectivityTestingTab] = useState<ModelConfigTab | null>(null);
  const [connectivityResultsByTab, setConnectivityResultsByTab] = useState<
    Partial<Record<ModelConfigTab, ModelProfileConnectivityResult[]>>
  >({});
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [isCreatingNewProfile, setIsCreatingNewProfile] = useState(false);
  const [modelProfileForm] = Form.useForm();
  const [treePanelWidth, setTreePanelWidth] = useState(initialTreePanelWidth);
  const [agentPanelWidth, setAgentPanelWidth] = useState(initialAgentPanelWidth);
  const [treePanelCollapsed, setTreePanelCollapsed] = useState(initialTreePanelCollapsed);
  const [nodesRefreshing, setNodesRefreshing] = useState(false);
  const treeResizeStart = useRef<{ startX: number; startWidth: number } | null>(null);
  const agentResizeStart = useRef<{ startX: number; startWidth: number } | null>(null);
  const pendingTreePanelWidthRef = useRef<number | null>(null);
  const pendingAgentPanelWidthRef = useRef<number | null>(null);

  function setActiveDocumentId(nextDocumentId: string | null) {
    setDocumentId((current) => {
      if (current === nextDocumentId) {
        return current;
      }
      setDocumentLoading(nextDocumentId != null);
      setStoredDocumentId(novelId, nextDocumentId);
      return nextDocumentId;
    });
  }

  function handleEmbeddingProviderChange(providerKind: string) {
    if (providerKind !== "ollama") {
      return;
    }
    modelProfileForm.setFieldsValue({
      embedding_base_url: ollamaDefaults.baseUrl,
      embedding_model: ollamaDefaults.embeddingModel,
    });
  }

  function handleTreeResizeStart(event: ReactMouseEvent<HTMLDivElement>) {
    treeResizeStart.current = { startWidth: treePanelWidth, startX: event.clientX };
    event.preventDefault();
  }

  function handleAgentResizeStart(event: ReactMouseEvent<HTMLDivElement>) {
    agentResizeStart.current = { startWidth: agentPanelWidth, startX: event.clientX };
    event.preventDefault();
  }

  function setTreeCollapsed(collapsed: boolean) {
    setTreePanelCollapsed(collapsed);
    window.localStorage.setItem(treePanelCollapsedStorageKey, String(collapsed));
  }

  useEffect(() => {
    function handleMouseMove(event: MouseEvent) {
      if (!treeResizeStart.current) {
        if (!agentResizeStart.current) {
          return;
        }
        const nextWidth = clampAgentPanelWidth(
          agentResizeStart.current.startWidth + agentResizeStart.current.startX - event.clientX,
        );
        pendingAgentPanelWidthRef.current = nextWidth;
        setAgentPanelWidth(nextWidth);
        return;
      }
      const nextWidth = clampTreePanelWidth(
        treeResizeStart.current.startWidth + event.clientX - treeResizeStart.current.startX,
      );
      pendingTreePanelWidthRef.current = nextWidth;
      setTreePanelWidth(nextWidth);
    }

    function handleMouseUp() {
      if (pendingTreePanelWidthRef.current !== null) {
        window.localStorage.setItem(treePanelWidthStorageKey, String(pendingTreePanelWidthRef.current));
        pendingTreePanelWidthRef.current = null;
      }
      if (pendingAgentPanelWidthRef.current !== null) {
        window.localStorage.setItem(agentPanelWidthStorageKey, String(pendingAgentPanelWidthRef.current));
        pendingAgentPanelWidthRef.current = null;
      }
      treeResizeStart.current = null;
      agentResizeStart.current = null;
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    setIsCreatingNewProfile(false);
  }, [novelId]);

  useEffect(() => {
    setActiveDocumentId(getStoredDocumentId(novelId));
  }, [novelId]);

  useEffect(() => {
    onPendingConfirmationCountChange?.(confirmationCount);
  }, [confirmationCount, onPendingConfirmationCountChange]);

  useEffect(() => {
    function handleSearchShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setNovelSearchOpen(true);
      }
    }

    window.addEventListener("keydown", handleSearchShortcut);
    return () => {
      window.removeEventListener("keydown", handleSearchShortcut);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      try {
        const [
          loadedNodes,
          confirmations,
          loadedConfirmationHistory,
          memories,
          modelProfiles,
          assets,
          events,
          states,
          attributes,
          inventory,
          mapLocations,
          relationships,
          changes,
        ] = await Promise.all([
          listWorkspaceNodes(token, novelId),
          listConfirmations(token, novelId),
          loadConfirmationHistorySafe(token, novelId),
          listMemoryItems(token, novelId),
          listModelProfiles(token),
          listCreativeAssets(token, novelId),
          listTimelineEvents(token, novelId),
          listCharacterStates(token, novelId),
          listCharacterAttributes(token, novelId),
          listInventoryItems(token, novelId),
          listMapLocations(token, novelId),
          listRelationshipEdges(token, novelId),
          listMaterialChanges(token, novelId),
        ]);
        if (!cancelled) {
          setNodes(loadedNodes);
          const resolvedDocumentId = (() => {
            const storedDocumentId = getStoredDocumentId(novelId);
            if (
              storedDocumentId &&
              loadedNodes.some(
                (node) => node.document_id === storedDocumentId && node.status !== "trashed",
              )
            ) {
              return storedDocumentId;
            }
            return (
              loadedNodes.find((node) => node.document_id && node.status !== "trashed")?.document_id ??
              null
            );
          })();
          setActiveDocumentId(resolvedDocumentId);
          setConfirmations(confirmations);
          setConfirmationHistory(loadedConfirmationHistory);
          setMemoryItems(memories);
          setModelProfiles(modelProfiles);
          setCreativeAssets(assets);
          setTimelineEvents(events);
          setCharacterStates(states);
          setCharacterAttributes(attributes);
          setInventoryItems(inventory);
          setMapLocations(mapLocations);
          setRelationshipEdges(relationships);
          setMaterialChanges(changes);
          setConfirmationCount(confirmations.filter((item) => item.status === "pending").length);
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
    if (isCreatingNewProfile || modelProfiles.length === 0 || !defaultModelProfileId) {
      return;
    }
    const profile = modelProfiles.find((item) => item.id === defaultModelProfileId);
    if (!profile) {
      return;
    }
    setEditingProfileId(profile.id);
    modelProfileForm.setFieldsValue(profileToFormValues(profile));
  }, [defaultModelProfileId, isCreatingNewProfile, modelProfileForm, modelProfiles]);

  useEffect(() => {
    if (!documentId) {
      setDocument(null);
      setVersions([]);
      setDocumentLoading(false);
      return;
    }

    let cancelled = false;
    setDocumentLoading(true);

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
      } finally {
        if (!cancelled) {
          setDocumentLoading(false);
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
      message.warning("请先选择要保存的章节。");
      return;
    }
    setSaving(true);
    try {
      const saved = await updateDocument(token, documentId, content);
      const loadedVersions = await listDocumentVersions(token, documentId);
      setDocument(saved);
      setVersions(loadedVersions);
      setDraftRevision(draftTrackerRef.current.clearDraft(documentId));
      message.success("章节已保存");
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : "保存章节失败";
      message.error(detail);
    } finally {
      setSaving(false);
    }
  }

  function handleDocumentDraftChange(content: DocumentBody) {
    if (!documentId || documentLoading || document?.id !== documentId) {
      return;
    }
    const { dirtyChanged, revision } = draftTrackerRef.current.updateDraft(
      documentId,
      content,
      document.content,
    );
    if (dirtyChanged) {
      setDraftRevision(revision);
    }
    scheduleWordCountUpdateRef.current(content);
  }

  async function handleRestoreDocumentVersion(versionId: string) {
    if (!documentId) {
      return;
    }
    setRestoringVersionId(versionId);
    try {
      const restored = await restoreDocumentVersion(token, documentId, versionId);
      const loadedVersions = await listDocumentVersions(token, documentId);
      setDocument(restored);
      setVersions(loadedVersions);
      setDraftRevision(draftTrackerRef.current.clearDraft(documentId));
      setVersionHistoryOpen(false);
      message.success("已恢复到此版本");
    } catch (error) {
      const detail = error instanceof ApiError ? error.message : "恢复版本失败";
      message.error(detail);
    } finally {
      setRestoringVersionId(null);
    }
  }

  async function refreshReviewQueues() {
    const [loadedConfirmations, loadedConfirmationHistory, loadedMemoryItems] = await Promise.all([
      listConfirmations(token, novelId),
      loadConfirmationHistorySafe(token, novelId),
      listMemoryItems(token, novelId),
    ]);
    setConfirmations(loadedConfirmations);
    setConfirmationHistory(loadedConfirmationHistory);
    setMemoryItems(loadedMemoryItems);
    setConfirmationCount(loadedConfirmations.filter((item) => item.status === "pending").length);
  }

  async function refreshCreativeCollections() {
    const [assets, events, states, attributes, inventory, mapLocations, relationships, changes] = await Promise.all([
      listCreativeAssets(token, novelId),
      listTimelineEvents(token, novelId),
      listCharacterStates(token, novelId),
      listCharacterAttributes(token, novelId),
      listInventoryItems(token, novelId),
      listMapLocations(token, novelId),
      listRelationshipEdges(token, novelId),
      listMaterialChanges(token, novelId),
    ]);
    setCreativeAssets(assets);
    setTimelineEvents(events);
    setCharacterStates(states);
    setCharacterAttributes(attributes);
    setInventoryItems(inventory);
    setMapLocations(mapLocations);
    setRelationshipEdges(relationships);
    setMaterialChanges(changes);
  }

  async function refreshWorkspaceNodes() {
    const loadedNodes = await listWorkspaceNodes(token, novelId);
    setNodes(loadedNodes);
  }

  async function handleRefreshWorkspaceNodes() {
    setNodesRefreshing(true);
    try {
      await refreshWorkspaceNodes();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "刷新章节失败");
    } finally {
      setNodesRefreshing(false);
    }
  }

  async function reloadActiveDocument() {
    if (!documentId) {
      return;
    }
    setDocumentLoading(true);
    try {
      const [loadedDocument, loadedVersions] = await Promise.all([
        getDocument(token, documentId),
        listDocumentVersions(token, documentId),
      ]);
      setDocument(loadedDocument);
      setVersions(loadedVersions);
      setDraftRevision(draftTrackerRef.current.clearDraft(documentId));
    } catch {
      setDocument(null);
      setVersions([]);
    } finally {
      setDocumentLoading(false);
    }
  }

  async function resolveConfirmation(confirmationId: string, action: "approve" | "reject") {
    if (action === "approve" && hasUnsavedDraft) {
      message.warning("当前章节有未保存的本地修改。请先保存或撤销修改，再让 Agent 重新生成写入方案。");
      return;
    }
    let resolved: Confirmation | null = null;
    try {
      if (action === "approve") {
        resolved = await approveConfirmation(token, confirmationId);
      } else {
        resolved = await rejectConfirmation(token, confirmationId);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await refreshReviewQueues();
      }
      throw error;
    }
    await refreshReviewQueues();
    const changedDocumentId = resolved.document_id ?? documentId;
    if (changedDocumentId) {
      const [loadedDocument, loadedVersions] = await Promise.all([
        getDocument(token, changedDocumentId),
        listDocumentVersions(token, changedDocumentId),
      ]);
      if (changedDocumentId === documentId) {
        setDocument(loadedDocument);
        setVersions(loadedVersions);
        setDraftRevision(draftTrackerRef.current.clearDraft(changedDocumentId));
      }
    }
  }

  async function removeMemory(itemId: string) {
    try {
      await deleteMemoryItem(token, itemId);
      setMemoryItems((items) => items.filter((item) => item.id !== itemId));
    } catch {
      message.error("删除记忆失败");
    }
  }

  async function handleUpdateCreativeAsset(
    assetId: string,
    payload: Pick<CreativeAsset, "asset_type" | "name" | "summary">,
  ) {
    try {
      const updated = await updateCreativeAsset(token, novelId, assetId, payload);
      setCreativeAssets((items) => items.map((item) => (item.id === assetId ? updated : item)));
      const changes = await listMaterialChanges(token, novelId);
      setMaterialChanges(changes);
      message.success("创作资产已更新");
    } catch {
      message.error("更新创作资产失败");
    }
  }

  async function handleDeleteCreativeAsset(assetId: string) {
    try {
      await deleteCreativeAsset(token, novelId, assetId);
      setCreativeAssets((items) => items.filter((item) => item.id !== assetId));
      const changes = await listMaterialChanges(token, novelId);
      setMaterialChanges(changes);
      message.success("创作资产已删除");
    } catch {
      message.error("删除创作资产失败");
    }
  }

  async function handleUpsertCharacterAttribute(payload: CharacterAttributePayload) {
    try {
      const saved = await upsertCharacterAttribute(token, novelId, payload);
      setCharacterAttributes((items) => {
        const exists = items.some((item) => item.id === saved.id);
        return exists ? items.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...items];
      });
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("人物属性已保存");
    } catch {
      message.error("保存人物属性失败");
    }
  }

  async function handleUpdateCharacterAttribute(attributeId: string, payload: Partial<CharacterAttributePayload>) {
    try {
      const updated = await updateCharacterAttribute(token, novelId, attributeId, payload);
      setCharacterAttributes((items) => items.map((item) => (item.id === attributeId ? updated : item)));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("人物属性已更新");
    } catch {
      message.error("更新人物属性失败");
    }
  }

  async function handleDeleteCharacterAttribute(attributeId: string) {
    try {
      await deleteCharacterAttribute(token, novelId, attributeId);
      setCharacterAttributes((items) => items.filter((item) => item.id !== attributeId));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("人物属性已删除");
    } catch {
      message.error("删除人物属性失败");
    }
  }

  async function handleUpsertInventoryItem(payload: InventoryItemPayload) {
    try {
      const saved = await upsertInventoryItem(token, novelId, payload);
      setInventoryItems((items) => {
        const exists = items.some((item) => item.id === saved.id);
        return exists ? items.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...items];
      });
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("背包物品已保存");
    } catch {
      message.error("保存背包物品失败");
    }
  }

  async function handleUpdateInventoryItem(itemId: string, payload: Partial<InventoryItemPayload>) {
    try {
      const updated = await updateInventoryItem(token, novelId, itemId, payload);
      setInventoryItems((items) => items.map((item) => (item.id === itemId ? updated : item)));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("背包物品已更新");
    } catch {
      message.error("更新背包物品失败");
    }
  }

  async function handleDeleteInventoryItem(itemId: string) {
    try {
      await deleteInventoryItem(token, novelId, itemId);
      setInventoryItems((items) => items.filter((item) => item.id !== itemId));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("背包物品已删除");
    } catch {
      message.error("删除背包物品失败");
    }
  }

  async function handleUpsertMapLocation(payload: MapLocationPayload) {
    try {
      const saved = await upsertMapLocation(token, novelId, payload);
      setMapLocations((items) => {
        const exists = items.some((item) => item.id === saved.id);
        return exists ? items.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...items];
      });
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("地图地点已保存");
    } catch {
      message.error("保存地图地点失败");
    }
  }

  async function handleUpdateMapLocation(locationId: string, payload: Partial<MapLocationPayload>) {
    try {
      const updated = await updateMapLocation(token, novelId, locationId, payload);
      setMapLocations((items) => items.map((item) => (item.id === locationId ? updated : item)));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("地图地点已更新");
    } catch {
      message.error("更新地图地点失败");
    }
  }

  async function handleDeleteMapLocation(locationId: string) {
    try {
      await deleteMapLocation(token, novelId, locationId);
      setMapLocations((items) => items.filter((item) => item.id !== locationId));
      setMaterialChanges(await listMaterialChanges(token, novelId));
      message.success("地图地点已删除");
    } catch {
      message.error("删除地图地点失败");
    }
  }

  function handleSelectDocument(nextDocumentId: string) {
    selectDocument(nextDocumentId);
    if (activeSection !== "workspace") {
      onActiveSectionChange?.("workspace");
    }
  }

  function handleSearchHit(hit: DocumentSearchHit) {
    setNovelSearchOpen(false);
    if (hit.match_source === "body" && hit.match_length > 0) {
      setFocusSearchRange({ matchIndex: hit.match_index, matchLength: hit.match_length });
    } else {
      setFocusSearchRange({ matchIndex: 0, matchLength: 0 });
    }
    handleSelectDocument(hit.document_id);
  }

  function locatePendingConfirmation(confirmation: Confirmation) {
    if (!confirmation.document_id) {
      return;
    }
    setFocusConfirmationId(confirmation.id);
    handleSelectDocument(confirmation.document_id);
  }

  function locateFirstPendingWriteForDocument(documentId: string) {
    const confirmation = pendingDocumentWriteConfirmations(confirmations).find(
      (item) => item.document_id === documentId,
    );
    if (confirmation) {
      locatePendingConfirmation(confirmation);
      return;
    }
    handleSelectDocument(documentId);
  }

  function selectDocument(nextDocumentId: string | null) {
    setActiveDocumentId(nextDocumentId);
  }

  function buildModelProfilePayload(
    values: {
    api_key?: string;
    base_url?: string;
    chat_api_key?: string;
    chat_base_url?: string;
    chat_model: string;
    chat_provider_kind?: string;
    embedding_api_key?: string;
    embedding_base_url?: string;
    embedding_model?: string;
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
  },
    options?: { forUpdate?: boolean },
  ) {
    const normalized = normalizeEmbeddingConfig(values);
    const payload: Record<string, unknown> = {
      ...normalized,
      base_url: normalized.base_url || null,
      chat_base_url: normalized.chat_base_url || null,
      chat_provider_kind: normalized.chat_provider_kind || null,
      embedding_base_url: normalized.embedding_base_url || null,
      embedding_model: normalized.embedding_model?.trim() || "",
      embedding_provider_kind: normalized.embedding_provider_kind || null,
      summary_base_url: normalized.summary_base_url || null,
      summary_provider_kind: normalized.summary_provider_kind || null,
      writing_base_url: normalized.writing_base_url || null,
      writing_provider_kind: normalized.writing_provider_kind || null,
    };
    if (normalized.api_key) {
      payload.api_key = normalized.api_key;
    }
    if (normalized.chat_api_key) {
      payload.chat_api_key = normalized.chat_api_key;
    }
    if (normalized.embedding_api_key) {
      payload.embedding_api_key = normalized.embedding_api_key;
    }
    if (normalized.summary_api_key) {
      payload.summary_api_key = normalized.summary_api_key;
    }
    if (normalized.writing_api_key) {
      payload.writing_api_key = normalized.writing_api_key;
    }
    if (options?.forUpdate) {
      for (const field of optionalPurposeFields) {
        if (payload[field] === null || payload[field] === undefined) {
          delete payload[field];
        }
      }
    }
    return payload as typeof values & {
      embedding_model: string;
      embedding_provider_kind: string | null;
    };
  }

  async function handleSaveModelProfile(values: {
    api_key?: string;
    base_url?: string;
    chat_api_key?: string;
    chat_base_url?: string;
    chat_model: string;
    chat_provider_kind?: string;
    embedding_api_key?: string;
    embedding_base_url?: string;
    embedding_model?: string;
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
    if (!editingProfileId && !values.api_key) {
      message.error("新建配置时请填写默认 API Key");
      return;
    }

    setModelProfileSaving(true);
    try {
      const wasEditing = Boolean(editingProfileId);
      const payload = buildModelProfilePayload(values, { forUpdate: Boolean(editingProfileId) });
      const profile = editingProfileId
        ? await updateModelProfile(token, editingProfileId, payload)
        : await createModelProfile(token, {
            ...payload,
            api_key: values.api_key as string,
            context_window: 128000,
            embedding_dimensions: 1536,
            supports_json_mode: true,
            supports_streaming: true,
            supports_tool_calling: true,
          });
      setModelProfiles((current) =>
        wasEditing
          ? current.map((item) => (item.id === profile.id ? profile : item))
          : [...current, profile],
      );
      if (!wasEditing) {
        setModelProfileCount((current) => current + 1);
      }
      setIsCreatingNewProfile(false);
      await handleSelectDefaultModelProfile(profile.id);
      setEditingProfileId(profile.id);
      modelProfileForm.setFieldsValue(profileToFormValues(profile));
      message.success(wasEditing ? "模型配置已更新" : "模型配置已保存");
    } finally {
      setModelProfileSaving(false);
    }
  }

  async function handleSelectDefaultModelProfile(profileId: string | null) {
    await updateNovel(token, novelId, { default_model_profile_id: profileId });
    onDefaultModelProfileChange?.(profileId);
  }

  function handleStartNewModelProfile() {
    setIsCreatingNewProfile(true);
    setEditingProfileId(null);
    setConnectivityResultsByTab({});
    modelProfileForm.resetFields();
    modelProfileForm.setFieldsValue(defaultModelProfileFormValues);
  }

  function handleEditModelProfile(profile: ModelProfile) {
    setIsCreatingNewProfile(false);
    setEditingProfileId(profile.id);
    setConnectivityResultsByTab({});
    modelProfileForm.setFieldsValue(profileToFormValues(profile));
  }

  async function handleSwitchModelProfile(profile: ModelProfile) {
    if (defaultModelProfileId === profile.id) {
      return;
    }
    await handleSelectDefaultModelProfile(profile.id);
    handleEditModelProfile(profile);
    message.success(`已切换为「${profile.name}」`);
  }

  async function handleDeleteModelProfile(profile: ModelProfile) {
    await deleteModelProfile(token, profile.id);
    setModelProfiles((current) => current.filter((item) => item.id !== profile.id));
    setModelProfileCount((current) => Math.max(0, current - 1));
    if (defaultModelProfileId === profile.id) {
      await handleSelectDefaultModelProfile(null);
    }
    if (editingProfileId === profile.id) {
      handleStartNewModelProfile();
    }
    message.success("模型配置已删除");
  }

  async function handleSelectActiveModelProfile(profileId: string | null) {
    await handleSelectDefaultModelProfile(profileId);
    if (!profileId) {
      handleStartNewModelProfile();
      return;
    }
    const profile = modelProfiles.find((item) => item.id === profileId);
    if (profile) {
      handleEditModelProfile(profile);
    }
  }

  async function handleTestModelTabConnectivity(tab: ModelConfigTab) {
    const fields = modelTabValidateFields(tab, Boolean(editingProfileId));
    try {
      await modelProfileForm.validateFields(fields);
    } catch {
      return;
    }
    const values = modelProfileForm.getFieldsValue(true) as Parameters<typeof handleSaveModelProfile>[0];
    if (!editingProfileId && !values.api_key) {
      message.error("新建配置时请填写默认 API Key");
      return;
    }
    if (
      tab === "embedding" &&
      values.embedding_model?.trim() &&
      !values.embedding_provider_kind &&
      !values.embedding_base_url?.includes("11434")
    ) {
      message.error("请先选择向量场景供应商");
      return;
    }

    setConnectivityTestingTab(tab);
    try {
      const response = await testModelProfileConnectivity(token, {
        ...buildModelProfilePayload(values, { forUpdate: Boolean(editingProfileId) }),
        profile_id: editingProfileId,
        api_key: values.api_key,
        chat_model: values.chat_model,
        embedding_model: values.embedding_model?.trim() || "",
        name: values.name,
        provider_kind: values.provider_kind,
        purposes: MODEL_TAB_PURPOSES[tab],
        summary_model: values.summary_model,
        writing_model: values.writing_model,
      });
      setConnectivityResultsByTab((current) => ({ ...current, [tab]: response.results }));
      if (response.results.every((result) => result.ok)) {
        message.success("当前页模型连通正常");
      } else {
        message.warning("当前页部分模型连通失败，请查看测试结果");
      }
    } catch (error) {
      setConnectivityResultsByTab((current) => ({ ...current, [tab]: [] }));
      message.error(error instanceof Error ? error.message : "连通性测试失败");
    } finally {
      setConnectivityTestingTab(null);
    }
  }

  function renderModelTabConnectivity(tab: ModelConfigTab) {
    const results = connectivityResultsByTab[tab] ?? [];
    return (
      <Space data-testid={`model-tab-connectivity-${tab}`} direction="vertical" size={8} style={{ marginTop: 16, width: "100%" }}>
        <Button
          loading={connectivityTestingTab === tab}
          onClick={() => void handleTestModelTabConnectivity(tab)}
          type="default"
        >
          测试连通性
        </Button>
        {results.length > 0 ? (
          <List
            dataSource={results}
            renderItem={(result) => (
              <List.Item style={{ paddingInline: 0 }}>
                <Space direction="vertical" size={2} style={{ width: "100%" }}>
                  <Space wrap>
                    <Tag color={result.ok ? "success" : "error"}>{result.label}</Tag>
                    <Typography.Text>{result.model}</Typography.Text>
                  </Space>
                  <Typography.Text type={result.ok ? "success" : "danger"}>{result.message}</Typography.Text>
                </Space>
              </List.Item>
            )}
            size="small"
          />
        ) : null}
      </Space>
    );
  }

  async function handleExportWorkspaceNode(nodeId: string, title: string) {
    const blob = await exportWorkspaceNode(token, novelId, nodeId, "txt");
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${title}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleCreateWorkspaceNode(nodeType: "chapter" | "folder", parentId: string | null = null) {
    const title = nodeType === "chapter" ? "新章节" : "新文件夹";
    const node = await createWorkspaceNode(token, novelId, title, nodeType, parentId);
    setNodes((current) => [...current, node]);
    if (node.document_id) {
      selectDocument(node.document_id);
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
      selectDocument(nextDocumentId);
    }
  }

  async function handleEmptyWorkspaceTrash() {
    const deletedDocumentIds = new Set(
      nodes
        .filter((node) => node.status === "trashed")
        .flatMap((node) => collectNodeAndDescendants(node.id))
        .map((node) => node.document_id)
        .filter((documentId): documentId is string => Boolean(documentId)),
    );
    const result = await emptyWorkspaceTrash(token, novelId);
    const refreshedNodes = await listWorkspaceNodes(token, novelId);
    setNodes(refreshedNodes);
    if (documentId && deletedDocumentIds.has(documentId)) {
      selectDocument(refreshedNodes.find((node) => node.status !== "trashed" && node.document_id)?.document_id ?? null);
    }
    message.success(result.deleted_count > 0 ? `已清空 ${result.deleted_count} 个回收站项目` : "回收站已经是空的");
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
  const editorContent = useMemo(() => {
    if (!documentId) {
      return null;
    }
    return draftTrackerRef.current.getDraft(documentId) ?? serverDocumentContent;
  }, [documentId, draftRevision, serverDocumentContent]);
  const hasUnsavedDraft = useMemo(
    () => draftTrackerRef.current.isDirty(documentId),
    [documentId, draftRevision],
  );
  const visibleTimelineEvents = useMemo(() => prepareTimelineEvents(timelineEvents), [timelineEvents]);
  const hiddenTimelineDuplicateCount = Math.max(0, timelineEvents.length - visibleTimelineEvents.length);
  const activeNodes = useMemo(() => nodes.filter((node) => node.status !== "trashed"), [nodes]);
  const chapterCount = activeNodes.filter((node) => node.node_type !== "folder").length;
  const folderCount = activeNodes.filter((node) => node.node_type === "folder").length;

  useEffect(() => {
    setCurrentWordCount(extractDocumentBodyText(serverDocumentContent).length);
  }, [documentId, serverDocumentContent]);
  const currentChapterNode = useMemo(
    () => nodes.find((node) => node.document_id === documentId) ?? null,
    [documentId, nodes],
  );
  const currentChapterTitle = currentChapterNode?.title ?? null;
  const chapterNodes = useMemo(
    () => activeNodes.filter((node) => node.node_type === "chapter" && Boolean(node.document_id)),
    [activeNodes],
  );
  async function handleScoreChapters() {
    const nodeIds =
      scoringScope === "all"
        ? []
        : scoringScope === "current"
          ? currentChapterNode
            ? [currentChapterNode.id]
            : []
          : selectedScoringNodeIds;
    if (scoringScope !== "all" && nodeIds.length === 0) {
      message.warning("请先选择要评分的章节");
      return;
    }
    setChapterScoring(true);
    try {
      const response = await runAgentTool<ChapterScoreResult>(token, novelId, "score_chapters_with_rubric", {
        scope: scoringScope === "all" ? "all" : "selected",
        node_ids: nodeIds,
      });
      setChapterScoreResult(response.result);
      message.success("评分完成");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "评分失败");
    } finally {
      setChapterScoring(false);
    }
  }
  const pendingWriteConfirmations = useMemo(
    () => pendingDocumentWriteConfirmations(confirmations),
    [confirmations],
  );
  const pendingWriteCountsByDocumentId = useMemo(
    () => pendingDocumentWriteCountsByDocumentId(confirmations),
    [confirmations],
  );
  const currentChapterConfirmations = useMemo(
    () => pendingWriteConfirmations.filter((confirmation) => confirmation.document_id === documentId),
    [documentId, pendingWriteConfirmations],
  );
  const editorLoading = documentLoading || agentDocumentWriteLocked;

  const handleAgentRunCompleted = useCallback(async (payload: AgentStreamDonePayload) => {
    const tasks: Promise<unknown>[] = [refreshReviewQueues()];
    if (payload.confirmation) {
      tasks.push(reloadActiveDocument());
    }
    const toolCalls = payload.tool_calls ?? [];
    if (toolCalls.some((call) => MATERIAL_REFRESH_TOOLS.has(call.tool))) {
      tasks.push(refreshCreativeCollections());
    }
    if (!payload.workspace_nodes) {
      const touchedWorkspace = toolCalls.some((call) =>
        [
          "cleanup_workspace_folders",
          "create_chapter_with_content",
          "create_workspace_node",
          "organize_workspace_tree",
          "restore_workspace_node",
          "split_chapter_by_max_chars",
          "trash_workspace_node",
          "update_workspace_node",
        ].includes(call.tool),
      );
      if (touchedWorkspace) {
        tasks.push(refreshWorkspaceNodes());
      }
    }
    await Promise.all(tasks);
  }, [novelId, token, documentId]);

  const workspaceStats = (
    <Card
      data-testid="workspace-overview"
      size="small"
      style={{
        background: "linear-gradient(135deg, rgba(255,122,24,0.12), rgba(255,255,255,0.86))",
        border: "1px solid rgba(255,122,24,0.16)",
        borderRadius: 14,
        boxShadow: "0 12px 34px rgba(255,122,24,0.08)",
      }}
    >
      <div
        style={{
          alignItems: "center",
          display: "grid",
          gap: 10,
          gridTemplateColumns: treePanelCollapsed
            ? "auto 1.2fr repeat(4, minmax(72px, 1fr))"
            : "1.2fr repeat(4, minmax(72px, 1fr))",
        }}
      >
        {treePanelCollapsed ? (
          <Button
            aria-label="展开章节"
            icon={<RightOutlined style={{ fontSize: 10 }} />}
            onClick={() => setTreeCollapsed(false)}
            size="small"
            type="text"
            style={{
              background: "rgba(255,255,255,0.92)",
              border: "1px solid rgba(255,122,24,0.16)",
              borderRadius: 7,
              boxShadow: "0 2px 6px rgba(255,122,24,0.08)",
              color: "#ea580c",
              flexShrink: 0,
              height: 22,
              minWidth: 22,
              padding: 0,
              width: 22,
            }}
          />
        ) : null}
        <div>
          <Typography.Text strong>作品概览</Typography.Text>
          <Typography.Text style={{ color: "#f97316", display: "block", fontSize: 12 }}>今日也要稳定更新</Typography.Text>
        </div>
        <Statistic title="章节" value={chapterCount} styles={{ content: { color: "#111827", fontSize: 17 } }} />
        <Statistic title="文件夹" value={folderCount} styles={{ content: { color: "#111827", fontSize: 17 } }} />
        <Statistic title="当前字数" value={currentWordCount} styles={{ content: { color: "#111827", fontSize: 17 } }} />
        <div style={{ alignItems: "center", display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Tag color={hasUnsavedDraft ? "orange" : "green"} style={{ marginInlineEnd: 0 }}>
            {hasUnsavedDraft ? "有本地草稿" : "已同步"}
          </Tag>
          <Button
            aria-label="全小说搜索"
            data-testid="novel-search-open"
            icon={<SearchOutlined />}
            onClick={() => setNovelSearchOpen(true)}
            size="small"
          >
            搜索
          </Button>
        </div>
      </div>
    </Card>
  );

  const chapterTreePanel = (
    <WorkspaceTree
      nodes={nodes}
      onCollapse={() => setTreeCollapsed(true)}
      onCreateChapter={(parentId) => void handleCreateWorkspaceNode("chapter", parentId ?? null)}
      onCreateFolder={(parentId) => void handleCreateWorkspaceNode("folder", parentId ?? null)}
      onEmptyTrash={() => void handleEmptyWorkspaceTrash()}
      onMoveNode={(nodeId, parentId, position) =>
        void handleUpdateWorkspaceNode(nodeId, { parent_id: parentId, position })
      }
      onReorderNodes={(changes) => void handleReorderWorkspaceNodes(changes)}
      onExportNode={(nodeId, title) => void handleExportWorkspaceNode(nodeId, title)}
      onRenameNode={(nodeId, title) => void handleUpdateWorkspaceNode(nodeId, { title })}
      onRestoreNode={(nodeId) => void handleWorkspaceNodeStatus(nodeId, "draft")}
      onSelectDocument={handleSelectDocument}
      onLocatePendingWrites={locateFirstPendingWriteForDocument}
      onRefresh={() => void handleRefreshWorkspaceNodes()}
      pendingWriteCountsByDocumentId={pendingWriteCountsByDocumentId}
      refreshing={nodesRefreshing}
      selectedDocumentId={documentId}
      onTrashNode={(nodeId) => void handleWorkspaceNodeStatus(nodeId, "trashed")}
    />
  );

  const agentPanel = (
    <AgentPanel
      hasModelProfile={Boolean(defaultModelProfileId)}
      onOpenModelConfig={onOpenAgentConfig}
      token={token}
      novelId={novelId}
      documentId={documentId}
      onClearSelectedText={() => setSelectedText(null)}
      onDismissWorkspaceDiff={() => setWorkspaceDiff(null)}
      onRunCompleted={handleAgentRunCompleted}
      onNovelUpdated={onNovelUpdated}
      onDocumentWriteLockChange={setAgentDocumentWriteLocked}
      onWriteConfirmationCreated={(confirmation) => {
        if (confirmation.document_id) {
          selectDocument(confirmation.document_id);
        }
        setFocusConfirmationId(confirmation.id);
        setConfirmations((current) => {
          const nextItem: Confirmation = {
            id: confirmation.id,
            action_type: confirmation.action_type,
            status: confirmation.status,
            payload: confirmation.payload,
            document_id: confirmation.document_id ?? null,
            before_text:
              "before_text" in confirmation && typeof confirmation.before_text === "string"
                ? confirmation.before_text
                : null,
            after_text:
              "after_text" in confirmation && typeof confirmation.after_text === "string"
                ? confirmation.after_text
                : null,
          };
          if (current.some((item) => item.id === nextItem.id)) {
            return current;
          }
          return [...current, nextItem];
        });
        setConfirmationCount((count) => count + 1);
      }}
      onUndoWorkspaceDiff={() => void handleUndoWorkspaceDiff()}
      onWorkspaceOrganized={(updatedNodes, diff) => {
        const previousIds = new Set(nodes.map((node) => node.id));
        const createdNode = updatedNodes.find(
          (node) => !previousIds.has(node.id) && node.document_id && node.status !== "trashed",
        );
        setNodes(updatedNodes);
        setWorkspaceDiff(diff ?? null);
        if (createdNode?.document_id) {
          selectDocument(createdNode.document_id);
        }
      }}
      selectedText={selectedText}
      workspaceDiff={workspaceDiff}
    />
  );

  function renderWorkspaceShell(centerContent: ReactNode) {
    const gridTemplateColumns = treePanelCollapsed
      ? `minmax(0, 1fr) 6px ${agentPanelWidth}px`
      : `${treePanelWidth}px 6px minmax(0, 1fr) 6px ${agentPanelWidth}px`;
    return (
      <div
        data-testid="workspace-shell"
        style={{
          height: "100%",
          minHeight: 0,
          minWidth: 0,
        }}
      >
        <div
          data-testid="workspace-grid"
          style={{
            display: "grid",
            gap: 14,
            gridTemplateColumns,
            gridTemplateRows: "minmax(0, 1fr)",
            height: "100%",
            minHeight: 0,
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {treePanelCollapsed ? null : (
            <div style={{ height: "100%", minHeight: 0, minWidth: 0, overflow: "hidden" }}>{chapterTreePanel}</div>
          )}
          {treePanelCollapsed ? null : <div
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
          </div>}
          <div
            data-testid="workspace-editor-column"
            style={{
              display: "grid",
              gap: 10,
              gridTemplateRows: "auto minmax(0, 1fr)",
              height: "100%",
              minHeight: 0,
              minWidth: 0,
              overflow: "hidden",
              position: "relative",
            }}
          >
            {workspaceStats}
            <div
              style={{
                minHeight: 0,
                minWidth: 0,
                overflow: activeSection === "workspace" ? "hidden" : "auto",
              }}
            >
              {centerContent}
            </div>
          </div>
          <div
            aria-label="调整 Agent 面板宽度"
            aria-orientation="vertical"
            onMouseDown={handleAgentResizeStart}
            role="separator"
            style={{ alignSelf: "stretch", cursor: "col-resize", marginInline: -4, position: "relative", zIndex: 2 }}
          >
            <div style={{ background: "rgba(15,23,42,0.08)", borderRadius: 999, height: "100%", margin: "0 auto", width: 2 }} />
          </div>
          <div style={{ height: "100%", minHeight: 0, minWidth: 0, overflow: "hidden" }}>{agentPanel}</div>
        </div>
      </div>
    );
  }

  const workspaceCenterContent = (
    <>
      <div
        data-testid="workspace-chapter-panel"
        style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, minWidth: 0 }}
      >
        <DocumentEditor
          chapterTitle={currentChapterTitle}
          content={editorContent}
          documentId={documentId}
          focusConfirmationId={focusConfirmationId}
          focusSearchRange={focusSearchRange}
          loading={editorLoading}
          pendingConfirmations={currentChapterConfirmations}
          onApproveConfirmation={(confirmationId) =>
            void resolveConfirmation(confirmationId, "approve").catch((error: Error) =>
              message.error(error.message),
            )
          }
          onChange={handleDocumentDraftChange}
          onFocusConfirmationHandled={() => setFocusConfirmationId(null)}
          onFocusSearchHandled={() => setFocusSearchRange(null)}
          onOpenVersionHistory={() => setVersionHistoryOpen(true)}
          onRejectConfirmation={(confirmationId) =>
            void resolveConfirmation(confirmationId, "reject").catch((error: Error) =>
              message.error(error.message),
            )
          }
          onRenameChapter={(title) => {
            if (currentChapterNode) {
              void handleUpdateWorkspaceNode(currentChapterNode.id, { title });
            }
          }}
          onSave={handleSaveDocument}
          onSelectText={setSelectedText}
          saveStatus={saving ? "saving" : hasUnsavedDraft ? "dirty" : "saved"}
          saving={saving}
        />
      </div>
      <DocumentVersionHistory
        currentContent={editorContent}
        onClose={() => setVersionHistoryOpen(false)}
        onRestore={(versionId) => void handleRestoreDocumentVersion(versionId)}
        open={versionHistoryOpen}
        restoringVersionId={restoringVersionId}
        versions={versions}
      />
      <NovelSearchModal
        novelId={novelId}
        onClose={() => setNovelSearchOpen(false)}
        onSelectHit={handleSearchHit}
        open={novelSearchOpen}
        token={token}
      />
    </>
  );

  const agentConfigActionBar = (
    <Space
      data-testid="agent-config-actions"
      style={{
        background: "#ffffff",
        paddingBottom: 8,
        position: "sticky",
        top: 0,
        zIndex: 2,
      }}
      wrap
    >
      <Button loading={modelProfileSaving} onClick={() => modelProfileForm.submit()} type="primary">
        保存 Agent 配置
      </Button>
    </Space>
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
      {modelProfiles.length === 0 || !defaultModelProfileId ? (
        <Alert
          showIcon
          description="填写下方表单，在各 Tab 分别点「测试连通性」确认可用，再保存为当前小说的默认模型。"
          style={{ marginBottom: 16, maxWidth: 720 }}
          title="当前还没有可用的模型配置"
          type="warning"
        />
      ) : null}
      {agentConfigActionBar}
      <Form.Item label="当前小说使用" style={{ marginBottom: 16, marginTop: 16, maxWidth: 720 }}>
        <Select
          allowClear
          onChange={(value) => void handleSelectActiveModelProfile(value ?? null)}
          options={modelProfiles.map((profile) => ({ label: profile.name, value: profile.id }))}
          placeholder="选择模型配置"
          value={defaultModelProfileId ?? undefined}
        />
      </Form.Item>
      <Form
        form={modelProfileForm}
        initialValues={defaultModelProfileFormValues}
        layout="vertical"
        onFinish={handleSaveModelProfile}
        style={{ maxWidth: 720 }}
      >
        <Space style={{ marginBottom: 16, width: "100%" }}>
          <Typography.Text strong>{editingProfileId ? "编辑配置" : "新建配置"}</Typography.Text>
          {editingProfileId ? (
            <Button onClick={handleStartNewModelProfile} size="small" type="link">
              新建配置
            </Button>
          ) : null}
        </Space>
        <Form.Item label="配置名称" name="name" rules={[{ required: true, message: "请输入配置名称" }]}>
          <Input />
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
                    默认配置作为所有模型的回退。可在这里统一设置各场景模型；某个模型 Tab 不填供应商、模型、API Key 或 Base URL 时，会使用这里的值。
                  </Typography.Paragraph>
                  <Form.Item label="默认供应商" name="provider_kind" rules={[{ required: true, message: "请选择供应商" }]}>
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label="默认 Base URL（可选）" name="base_url">
                    <Input placeholder="https://api.openai.com/v1" />
                  </Form.Item>
                  <Form.Item
                    label="默认 API Key"
                    name="api_key"
                    rules={editingProfileId ? [] : [{ required: true, message: "请输入默认 API Key" }]}
                  >
                    <Input.Password placeholder={editingProfileId ? "留空则保持不变" : undefined} />
                  </Form.Item>
                  <Form.Item label="默认对话模型" name="chat_model" rules={[{ required: true, message: "请输入默认对话模型" }]}>
                    <Input placeholder="gpt-4o" />
                  </Form.Item>
                  <Form.Item label="默认写作模型" name="writing_model" rules={[{ required: true, message: "请输入默认写作模型" }]}>
                    <Input placeholder="gpt-4o" />
                  </Form.Item>
                  <Form.Item label="默认总结模型" name="summary_model" rules={[{ required: true, message: "请输入默认总结模型" }]}>
                    <Input placeholder="gpt-4o-mini" />
                  </Form.Item>
                  {renderModelTabConnectivity("default")}
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
                  <Form.Item label="对话模型" name="chat_model">
                    <Input placeholder="不填则使用默认对话模型" />
                  </Form.Item>
                  <Form.Item label="对话 Base URL" name="chat_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="对话 API Key" name="chat_api_key">
                    <Input.Password placeholder={editingProfileId ? "留空则保持不变" : "不填则使用默认 API Key"} />
                  </Form.Item>
                  {renderModelTabConnectivity("chat")}
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
                  <Form.Item label="写作模型" name="writing_model">
                    <Input placeholder="不填则使用默认写作模型" />
                  </Form.Item>
                  <Form.Item label="写作 Base URL" name="writing_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="写作 API Key" name="writing_api_key">
                    <Input.Password placeholder={editingProfileId ? "留空则保持不变" : "不填则使用默认 API Key"} />
                  </Form.Item>
                  {renderModelTabConnectivity("writing")}
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
                  <Form.Item label="总结模型" name="summary_model">
                    <Input placeholder="不填则使用默认总结模型" />
                  </Form.Item>
                  <Form.Item label="总结 Base URL" name="summary_base_url">
                    <Input placeholder="不填则使用默认 Base URL" />
                  </Form.Item>
                  <Form.Item label="总结 API Key" name="summary_api_key">
                    <Input.Password placeholder={editingProfileId ? "留空则保持不变" : "不填则使用默认 API Key"} />
                  </Form.Item>
                  {renderModelTabConnectivity("summary")}
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
                  <Form.Item label="向量模型" name="embedding_model">
                    <Input placeholder={`可选；Ollama 默认 ${ollamaDefaults.embeddingModel}`} />
                  </Form.Item>
                  <Form.Item label="向量 Base URL" name="embedding_base_url">
                    <Input placeholder={`Ollama 默认 ${ollamaDefaults.baseUrl}`} />
                  </Form.Item>
                  <Form.Item label="向量 API Key" name="embedding_api_key">
                    <Input.Password placeholder={editingProfileId ? "留空则保持不变" : "不填则使用默认 API Key"} />
                  </Form.Item>
                  {renderModelTabConnectivity("embedding")}
                </>
              ),
            },
          ]}
        />
      </Form>
      <List
        dataSource={modelProfiles}
        header={<strong>已配置模型</strong>}
        locale={{ emptyText: "还没有模型配置" }}
        renderItem={(profile) => {
          const fallbackProvider = profile.provider_kind;
          return (
            <List.Item
              actions={[
                defaultModelProfileId === profile.id ? (
                  <Tag key="active" color="green">
                    当前使用
                  </Tag>
                ) : (
                  <Button key="switch" onClick={() => void handleSwitchModelProfile(profile)} size="small" type="link">
                    设为当前
                  </Button>
                ),
                <Button key="edit" onClick={() => handleEditModelProfile(profile)} size="small" type="link">
                  编辑
                </Button>,
                <Popconfirm
                  cancelText="取消"
                  key="delete"
                  okText="删除"
                  okType="danger"
                  onConfirm={() => void handleDeleteModelProfile(profile)}
                  title={`确定删除「${profile.name}」吗？`}
                >
                  <Button danger size="small" type="link">
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                description={
                  <Space size={[8, 8]} wrap>
                    <Tag color="blue">对话 {providerLabel(profile.chat_provider_kind ?? fallbackProvider)} · {profile.chat_model}</Tag>
                    <Tag color="green">写作 {providerLabel(profile.writing_provider_kind ?? fallbackProvider)} · {profile.writing_model}</Tag>
                    <Tag color="purple">总结 {providerLabel(profile.summary_provider_kind ?? fallbackProvider)} · {profile.summary_model}</Tag>
                    <Tag color="orange">
                      向量{" "}
                      {profile.embedding_model?.trim()
                        ? `${embeddingProviderLabel(profile.embedding_provider_kind ?? (profile.embedding_base_url?.includes("11434") ? "ollama" : fallbackProvider))} · ${profile.embedding_model}`
                        : "未配置"}
                    </Tag>
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

  const memoryCenterContent = (
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
      <Typography.Paragraph>
        Agent 检测到的长期信息和你明确要求记录的内容会自动保存，你可以随时删除。
      </Typography.Paragraph>
      <Tag color="blue">{memoryItems.length} 条记忆</Tag>
      <Tag>{modelProfileCount} 个模型配置</Tag>
      <List
        dataSource={memoryItems}
        locale={{ emptyText: "还没有保存的记忆" }}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Popconfirm
                cancelText="取消"
                description="删除后，Agent 将无法再从长期记忆中检索它。"
                key="delete"
                okText="确认删除"
                onConfirm={() => void removeMemory(item.id)}
                title="删除这条记忆？"
              >
                <Button danger size="small">
                  删除
                </Button>
              </Popconfirm>,
            ]}
          >
            <List.Item.Meta
              description={
                <Space direction="vertical" size={4}>
                  <Typography.Paragraph style={{ marginBottom: 0 }}>{item.body}</Typography.Paragraph>
                  <Space>
                    <Tag color={item.memory_type === "context_snapshot" ? "purple" : "blue"}>
                      {item.memory_type}
                    </Tag>
                    <span>importance {item.importance}</span>
                  </Space>
                </Space>
              }
              title={item.title}
            />
          </List.Item>
        )}
        style={{ marginTop: 16 }}
      />
    </Card>
  );

  const confirmationsCenterContent = (
    <Card style={{ border: "none", boxShadow: "0 18px 45px rgba(15,23,42,0.08)" }}>
      <ConfirmationsPanel
        confirmationCount={confirmationCount}
        confirmationHistory={confirmationHistory}
        confirmations={confirmations}
        onApprove={(confirmationId) =>
          void resolveConfirmation(confirmationId, "approve").catch((error: Error) =>
            message.error(error.message),
          )
        }
        onLocate={locatePendingConfirmation}
        onReject={(confirmationId) =>
          void resolveConfirmation(confirmationId, "reject").catch((error: Error) =>
            message.error(error.message),
          )
        }
      />
    </Card>
  );

  const materialsCenterContent = (
    <MaterialsPanel
      characterAttributes={characterAttributes}
      characterStates={characterStates}
      creativeAssets={creativeAssets}
      inventoryItems={inventoryItems}
      mapLocations={mapLocations}
      materialChanges={materialChanges}
      onDeleteCharacterAttribute={handleDeleteCharacterAttribute}
      onDeleteCreativeAsset={handleDeleteCreativeAsset}
      onDeleteInventoryItem={handleDeleteInventoryItem}
      onDeleteMapLocation={handleDeleteMapLocation}
      onUpsertCharacterAttribute={handleUpsertCharacterAttribute}
      onUpsertInventoryItem={handleUpsertInventoryItem}
      onUpsertMapLocation={handleUpsertMapLocation}
      onUpdateCharacterAttribute={handleUpdateCharacterAttribute}
      onUpdateCreativeAsset={handleUpdateCreativeAsset}
      onUpdateInventoryItem={handleUpdateInventoryItem}
      onUpdateMapLocation={handleUpdateMapLocation}
      relationshipEdges={relationshipEdges}
      timelineEvents={visibleTimelineEvents}
    />
  );

  const scoringCenterContent = (
    <Card
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15,23,42,0.08)",
        height: "100%",
        minWidth: 0,
      }}
      styles={{ body: { height: "100%", overflow: "auto" } }}
    >
      <Flex align="center" justify="space-between" gap={16} wrap>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            章节评分
          </Typography.Title>
          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            通过 Agent 工具按平台 rubric 评分：钩子、推进、人物、冲突、语言原创，并标记低质内容风险。
          </Typography.Paragraph>
        </div>
        {chapterScoreResult ? (
          <Statistic
            precision={1}
            suffix="/ 10"
            title={`${chapterScoreResult.summary.chapter_count} 章平均分`}
            value={chapterScoreResult.summary.average_score}
          />
        ) : null}
      </Flex>
      <Space align="end" size={12} style={{ marginTop: 18, width: "100%" }} wrap>
        <div>
          <Typography.Text style={{ display: "block", marginBottom: 6 }}>评分范围</Typography.Text>
          <Select
            aria-label="评分范围"
            onChange={(value) => setScoringScope(value)}
            options={[
              { label: "全部章节", value: "all" },
              { label: "当前章节", value: "current" },
              { label: "指定章节", value: "selected" },
            ]}
            style={{ width: 160 }}
            value={scoringScope}
          />
        </div>
        {scoringScope === "selected" ? (
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 6 }}>选择章节</Typography.Text>
            <Select
              aria-label="选择章节"
              mode="multiple"
              onChange={setSelectedScoringNodeIds}
              options={chapterNodes.map((node) => ({ label: node.title, value: node.id }))}
              placeholder="选择一个或多个章节"
              style={{ minWidth: 260 }}
              value={selectedScoringNodeIds}
            />
          </div>
        ) : null}
        <Button loading={chapterScoring} onClick={() => void handleScoreChapters()} type="primary">
          开始评分
        </Button>
      </Space>
      <Alert
        title="评分说明"
        description="总分 10 分。平台风险会结合章节体量、解释性句式、系统数字密度、功能章倾向和人物代价不足来判断。"
        showIcon
        style={{ marginTop: 16 }}
        type="info"
      />
      {chapterScoreResult?.scores.length ? (
        <List
          dataSource={chapterScoreResult.scores}
          renderItem={(score) => (
            <List.Item style={{ alignItems: "stretch", paddingInline: 0 }}>
              <Card size="small" style={{ width: "100%" }}>
                <Flex align="start" justify="space-between" gap={12} wrap>
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{score.chapter_title}</Typography.Text>
                    <Tag color={score.platform_risk === "低" ? "green" : score.platform_risk === "中" ? "orange" : "red"}>
                      平台风险：{score.platform_risk}
                    </Tag>
                  </Space>
                  <Statistic precision={1} suffix="/ 10" title="总分" value={score.total_score} />
                </Flex>
                <Space size={[8, 8]} style={{ marginTop: 12 }} wrap>
                  <Tag>钩子：{score.details.hook}</Tag>
                  <Tag>推进：{score.details.progress}</Tag>
                  <Tag>人物：{score.details.character}</Tag>
                  <Tag>冲突：{score.details.conflict}</Tag>
                  <Tag>语言原创：{score.details.language_originality}</Tag>
                </Space>
                <Typography.Paragraph style={{ marginTop: 12, marginBottom: 4 }} type="secondary">
                  扣分原因：{score.reasons.join("；")}
                </Typography.Paragraph>
                <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
                  修改建议：{score.suggestions.join("；")}
                </Typography.Paragraph>
              </Card>
            </List.Item>
          )}
          style={{ marginTop: 16 }}
        />
      ) : (
        <Empty description="还没有评分结果" style={{ marginTop: 40 }} />
      )}
    </Card>
  );

  const timelineCenterContent = (
    <Card
      data-testid="timeline-card"
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15,23,42,0.08)",
        height: "100%",
        minWidth: 0,
      }}
      styles={{ body: { height: "100%", overflow: "auto" } }}
    >
      <Typography.Title level={3}>时间线</Typography.Title>
      <Typography.Paragraph type="secondary">
        梳理故事中的关键事件，按时间顺序回顾剧情脉络。
      </Typography.Paragraph>
      <Tag color="orange" style={{ marginBottom: 16 }}>
        {visibleTimelineEvents.length} 个事件
      </Tag>
      {hiddenTimelineDuplicateCount > 0 ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="secondary">
          已合并 {hiddenTimelineDuplicateCount} 条重复时间线，并按卷序重新排序。
        </Typography.Text>
      ) : null}
      {visibleTimelineEvents.length === 0 ? (
        <Empty description="还没有时间线事件，可以让 Agent 帮你梳理故事线" />
      ) : (
        <Timeline
          items={visibleTimelineEvents.map((event) => ({
            key: event.id,
            color: "#ff7a18",
            children: (
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {event.event_time}
                </Typography.Text>
                <Typography.Text strong>{event.title}</Typography.Text>
                {event.summary ? (
                  <Typography.Paragraph style={{ margin: 0 }} type="secondary">
                    {event.summary}
                  </Typography.Paragraph>
                ) : null}
              </Space>
            ),
          }))}
        />
      )}
    </Card>
  );

  const centerContentBySection: Record<WorkspaceSection, ReactNode> = {
    "agent-config": agentConfigContent,
    confirmations: confirmationsCenterContent,
    materials: materialsCenterContent,
    memory: memoryCenterContent,
    scoring: scoringCenterContent,
    timeline: timelineCenterContent,
    workspace: workspaceCenterContent,
  };

  return (
    <div
      style={{
        height: "100%",
        minHeight: 0,
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      {renderWorkspaceShell(centerContentBySection[activeSection])}
    </div>
  );
}
