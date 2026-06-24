import { HistoryOutlined } from "@ant-design/icons";
import { Button, Drawer, Empty, List, Modal, Space, Tag, Typography } from "antd";
import { useState } from "react";

import type { DocumentBody, DocumentVersion } from "../../api/documents";
import { diffText, type DiffDisplaySegment } from "../confirmations/textDiff";

type DocumentVersionHistoryProps = {
  currentContent?: DocumentBody | null;
  open: boolean;
  versions: DocumentVersion[];
  restoringVersionId?: string | null;
  onClose: () => void;
  onRestore: (versionId: string) => void;
};

function extractDocumentText(content: DocumentBody): string {
  const blockTypes = new Set(["paragraph", "heading", "blockquote", "codeBlock", "listItem"]);
  const blocks: string[] = [];

  function collectInlineText(node: unknown): string {
    if (Array.isArray(node)) {
      return node.map(collectInlineText).join("");
    }
    if (!node || typeof node !== "object") {
      return "";
    }
    const current = node as { content?: unknown; text?: unknown };
    if (typeof current.text === "string") {
      return current.text;
    }
    return current.content ? collectInlineText(current.content) : "";
  }

  function visit(node: unknown) {
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    if (!node || typeof node !== "object") {
      return;
    }
    const current = node as { content?: unknown; text?: unknown; type?: unknown };
    if (typeof current.type === "string" && blockTypes.has(current.type)) {
      const text = collectInlineText(current).trim();
      if (text) {
        blocks.push(text);
      }
      return;
    }
    if (current.content) {
      visit(current.content);
    }
  }

  visit(content);
  if (blocks.length > 0) {
    return blocks.join("\n");
  }
  return collectInlineText(content);
}

function versionSourceLabel(source: string) {
  return source === "user" ? "手动保存" : "自动快照";
}

function formatVersionTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未知时间";
  }
  return date.toLocaleString();
}

function versionPreview(content: DocumentBody) {
  const text = extractDocumentText(content).trim();
  if (!text) {
    return "（空白版本）";
  }
  return text.length > 120 ? `${text.slice(0, 120)}…` : text;
}

function segmentText(segment: DiffDisplaySegment, side: "left" | "right") {
  if (segment.kind === "equal") {
    return segment.text;
  }
  if (segment.kind === "delete") {
    return side === "left" ? segment.text : "";
  }
  if (segment.kind === "insert") {
    return side === "right" ? segment.text : "";
  }
  return side === "left" ? segment.before : segment.after;
}

function segmentStyle(segment: DiffDisplaySegment, side: "left" | "right") {
  const base = {
    borderRadius: 6,
    minHeight: 28,
    padding: "6px 8px",
    whiteSpace: "pre-wrap" as const,
  };
  if (segment.kind === "equal") {
    return { ...base, color: "#475569" };
  }
  if (segment.kind === "delete" || (segment.kind === "modify" && side === "left")) {
    return {
      ...base,
      background: "#fee2e2",
      color: "#991b1b",
      textDecoration: segment.kind === "delete" ? "line-through" : "none",
    };
  }
  if (segment.kind === "insert" || (segment.kind === "modify" && side === "right")) {
    return { ...base, background: "#dcfce7", color: "#166534" };
  }
  return { ...base, color: "#94a3b8" };
}

function VersionSideBySideDiff({ after, before }: { after: string; before: string }) {
  const segments = diffText(before, after);

  return (
    <div
      style={{
        display: "grid",
        columnGap: 12,
        rowGap: 8,
        gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
      }}
    >
      <Typography.Text strong>历史版本</Typography.Text>
      <Typography.Text strong>当前正文</Typography.Text>
      {segments.map((segment, index) => (
        <div data-testid="version-diff-row" key={`row-${index}`} style={{ display: "contents" }}>
          <div style={segmentStyle(segment, "left")}>{segmentText(segment, "left")}</div>
          <div style={segmentStyle(segment, "right")}>{segmentText(segment, "right")}</div>
        </div>
      ))}
    </div>
  );
}

export function DocumentVersionHistory({
  currentContent = null,
  open,
  versions,
  restoringVersionId = null,
  onClose,
  onRestore,
}: DocumentVersionHistoryProps) {
  const [comparedVersionId, setComparedVersionId] = useState<string | null>(null);
  const currentText = currentContent ? extractDocumentText(currentContent) : "";
  const comparedVersion = versions.find((version) => version.id === comparedVersionId) ?? null;
  const comparedVersionText = comparedVersion ? extractDocumentText(comparedVersion.content) : "";

  return (
    <>
      <Drawer
        destroyOnClose
        onClose={onClose}
        open={open}
        title={
          <Space size={8}>
            <HistoryOutlined />
            <span>版本历史</span>
            <Tag>{versions.length} 个版本</Tag>
          </Space>
        }
        width={560}
      >
        {versions.length === 0 ? (
          <Empty description="还没有保存过版本，手动保存后会出现在这里" />
        ) : (
          <>
            <Typography.Paragraph type="secondary">
              恢复版本前会自动为当前正文创建一个新快照。
            </Typography.Paragraph>
            <List
              dataSource={versions}
              renderItem={(version) => (
                <List.Item
                  actions={[
                    <Button key="diff" onClick={() => setComparedVersionId(version.id)} size="small" type="link">
                      对比当前
                    </Button>,
                    <Button
                      key="restore"
                      loading={restoringVersionId === version.id}
                      onClick={() => onRestore(version.id)}
                      size="small"
                      type="link"
                    >
                      恢复
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    description={
                      <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
                        {versionPreview(version.content)}
                      </Typography.Paragraph>
                    }
                    title={
                      <Space size={6} wrap>
                        <Typography.Text strong>{formatVersionTime(version.created_at)}</Typography.Text>
                        <Tag>{versionSourceLabel(version.source)}</Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </>
        )}
      </Drawer>
      <Modal
        destroyOnHidden
        footer={null}
        onCancel={() => setComparedVersionId(null)}
        open={comparedVersion !== null}
        title="版本对比"
        width={960}
      >
        <div data-testid="version-diff-modal" style={{ maxHeight: "70vh", overflow: "auto", paddingTop: 4 }}>
          <VersionSideBySideDiff after={currentText} before={comparedVersionText} />
        </div>
      </Modal>
    </>
  );
}
