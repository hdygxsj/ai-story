import { FileTextOutlined, FolderOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Space, Tree, Typography } from "antd";
import type { WorkspaceNode } from "../../api/workspace";

type WorkspaceTreeProps = {
  nodes?: WorkspaceNode[];
  onSelectDocument?: (documentId: string) => void;
};

const placeholderNodes: WorkspaceNode[] = [
  {
    id: "drafts",
    novel_id: "placeholder",
    parent_id: null,
    document_id: null,
    title: "Drafts",
    node_type: "folder",
    status: "draft",
    position: 0,
  },
  {
    id: "chapter-1",
    novel_id: "placeholder",
    parent_id: null,
    document_id: "chapter-1-doc",
    title: "Chapter 1",
    node_type: "chapter",
    status: "draft",
    position: 1,
  },
];

export function WorkspaceTree({ nodes = placeholderNodes, onSelectDocument }: WorkspaceTreeProps) {
  const treeData = nodes.map((node) => ({
    key: node.id,
    icon: node.node_type === "folder" ? <FolderOutlined /> : <FileTextOutlined />,
    title: node.title,
    documentId: node.document_id,
  }));

  return (
    <section aria-label="Workspace tree" style={{ height: "100%", padding: 16 }}>
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
        <div>
          <Typography.Title level={2} style={{ marginBottom: 0 }}>
            Workspace
          </Typography.Title>
          <Typography.Text type="secondary">Chapters, drafts, and notes</Typography.Text>
        </div>
        <Space>
          <Button icon={<PlusOutlined />} size="small" type="primary">
            New Chapter
          </Button>
          <Button icon={<FolderOutlined />} size="small">
            Folder
          </Button>
        </Space>
        <Tree
          blockNode
          defaultExpandAll
          showIcon
          treeData={treeData}
          onSelect={(selectedKeys) => {
            const selectedKey = String(selectedKeys[0] ?? "");
            const documentId = nodes.find((node) => node.id === selectedKey)?.document_id;
            if (documentId) {
              onSelectDocument?.(documentId);
            }
          }}
        />
      </Space>
    </section>
  );
}
