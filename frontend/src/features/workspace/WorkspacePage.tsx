import { Button, Card, Layout, List, Space, Tabs, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import { AgentPanel } from "../agent/AgentPanel";
import { DocumentEditor } from "../editor/DocumentEditor";
import { WorkspaceTree } from "./WorkspaceTree";
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
import { listModelProfiles } from "../../api/modelProfiles";
import type { WorkspaceNode } from "../../api/workspace";
import { listWorkspaceNodes } from "../../api/workspace";

type WorkspacePageProps = {
  token: string;
  novelId: string;
};

export function WorkspacePage({ token, novelId }: WorkspacePageProps) {
  const [nodes, setNodes] = useState<WorkspaceNode[]>([]);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [document, setDocument] = useState<DocumentRecord | null>(null);
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
  const [saving, setSaving] = useState(false);

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
          setDocumentId((current) => current ?? loadedNodes.find((node) => node.document_id)?.document_id ?? null);
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
    } finally {
      setSaving(false);
    }
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

  return (
    <Layout style={{ minHeight: "calc(100vh - 96px)" }}>
      <Layout.Sider theme="light" width={300}>
        <WorkspaceTree nodes={nodes} onSelectDocument={setDocumentId} />
      </Layout.Sider>
      <Layout.Content style={{ background: "#f5f5f5" }}>
        <DocumentEditor
          content={document?.content ?? null}
          onSave={handleSaveDocument}
          onSelectText={setSelectedText}
          saving={saving}
        />
      </Layout.Content>
      <Layout.Sider theme="light" width={420}>
        <Tabs
          defaultActiveKey="agent"
          items={[
            {
              key: "agent",
              label: "Agent",
              children: (
                <AgentPanel token={token} novelId={novelId} documentId={documentId} selectedText={selectedText} />
              ),
            },
            {
              key: "memory",
              label: "Memory",
              children: (
                <Card>
                  <Typography.Title level={3}>Memory</Typography.Title>
                  <Typography.Paragraph>
                    Key memories, character states, timeline events, and RAG context will be reviewed here.
                  </Typography.Paragraph>
                  <Tag color="blue">{memoryReviewCount} pending review</Tag>
                  <Tag>{modelProfileCount} model profiles</Tag>
                  <List
                    dataSource={memoryReviews}
                    locale={{ emptyText: "No pending memory reviews" }}
                    renderItem={(item) => (
                      <List.Item
                        actions={[
                          <Button size="small" onClick={() => void resolveMemoryReview(item.id, "approve")}>
                            Approve
                          </Button>,
                          <Button danger size="small" onClick={() => void resolveMemoryReview(item.id, "reject")}>
                            Reject
                          </Button>,
                        ]}
                      >
                        <List.Item.Meta
                          description={`${item.memory_type} · importance ${item.importance}`}
                          title={item.title}
                        />
                      </List.Item>
                    )}
                    style={{ marginTop: 16 }}
                  />
                  <List
                    dataSource={modelProfiles}
                    locale={{ emptyText: "No model profiles configured" }}
                    renderItem={(profile) => (
                      <List.Item>
                        <List.Item.Meta description={`${profile.provider_kind} · ${profile.chat_model}`} title={profile.name} />
                      </List.Item>
                    )}
                    style={{ marginTop: 16 }}
                  />
                </Card>
              ),
            },
            {
              key: "confirmations",
              label: "Confirmations",
              children: (
                <Card>
                  <Typography.Title level={3}>Confirmations</Typography.Title>
                  <Typography.Paragraph>
                    Agent write actions wait here until you approve or reject them.
                  </Typography.Paragraph>
                  <Space wrap>
                    <Tag color="gold">{confirmationCount} pending</Tag>
                    <Tag>{versions.length} saved versions</Tag>
                  </Space>
                  <List
                    dataSource={confirmations}
                    locale={{ emptyText: "No pending confirmations" }}
                    renderItem={(confirmation) => (
                      <List.Item
                        actions={[
                          <Button size="small" onClick={() => void resolveConfirmation(confirmation.id, "approve")}>
                            Approve
                          </Button>,
                          <Button danger size="small" onClick={() => void resolveConfirmation(confirmation.id, "reject")}>
                            Reject
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
              ),
            },
            {
              key: "materials",
              label: "Materials",
              children: (
                <Card>
                  <Typography.Title level={3}>Materials</Typography.Title>
                  <Typography.Paragraph>
                    Structured creative assets, timeline, character state, and relationships.
                  </Typography.Paragraph>
                  <List
                    dataSource={creativeAssets}
                    header={<strong>Creative Assets</strong>}
                    renderItem={(asset) => (
                      <List.Item>
                        <List.Item.Meta description={`${asset.asset_type} · ${asset.summary}`} title={asset.name} />
                      </List.Item>
                    )}
                  />
                  <List
                    dataSource={timelineEvents}
                    header={<strong>Timeline</strong>}
                    renderItem={(event) => (
                      <List.Item>
                        <List.Item.Meta description={event.event_time} title={event.title} />
                      </List.Item>
                    )}
                  />
                  <List
                    dataSource={characterStates}
                    header={<strong>Character States</strong>}
                    renderItem={(state) => (
                      <List.Item>
                        <List.Item.Meta description={state.character_name} title={state.state} />
                      </List.Item>
                    )}
                  />
                  <List
                    dataSource={relationshipEdges}
                    header={<strong>Relationship Edges</strong>}
                    renderItem={(edge) => (
                      <List.Item>
                        <List.Item.Meta
                          description={`${edge.source_character} -> ${edge.target_character}`}
                          title={edge.relationship_type}
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              ),
            },
          ]}
          style={{ padding: 16 }}
        />
      </Layout.Sider>
    </Layout>
  );
}
