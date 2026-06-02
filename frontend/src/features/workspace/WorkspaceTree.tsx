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
  return (
    <section aria-label="Workspace tree" style={{ borderRight: "1px solid #ddd", padding: 16 }}>
      <h2>Workspace</h2>
      <button type="button">New Chapter</button>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {nodes.map((node) => (
          <li key={node.id} style={{ marginTop: 8 }}>
            <button
              type="button"
              disabled={!node.document_id}
              onClick={() => node.document_id && onSelectDocument?.(node.document_id)}
            >
              {node.node_type === "folder" ? "Folder: " : "Chapter: "}
              {node.title}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
