import { HistoryOutlined } from "@ant-design/icons";
import { Button, Drawer, Empty, List, Space, Tag, Typography } from "antd";

import type { DocumentBody, DocumentVersion } from "../../api/documents";

type DocumentVersionHistoryProps = {
  open: boolean;
  versions: DocumentVersion[];
  restoringVersionId?: string | null;
  onClose: () => void;
  onRestore: (versionId: string) => void;
};

function extractDocumentText(content: DocumentBody): string {
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

export function DocumentVersionHistory({
  open,
  versions,
  restoringVersionId = null,
  onClose,
  onRestore,
}: DocumentVersionHistoryProps) {
  return (
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
      width={420}
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
  );
}
