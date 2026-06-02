import { useState } from "react";

import { AgentPanel } from "../agent/AgentPanel";
import { DocumentEditor } from "../editor/DocumentEditor";
import { WorkspaceTree } from "./WorkspaceTree";

type WorkspacePageProps = {
  token: string;
  novelId: string;
};

export function WorkspacePage({ token, novelId }: WorkspacePageProps) {
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [selectedText, setSelectedText] = useState<string | null>(null);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "260px minmax(360px, 1fr) 340px",
        minHeight: 620,
      }}
    >
      <WorkspaceTree onSelectDocument={setDocumentId} />
      <DocumentEditor onSelectText={setSelectedText} />
      <AgentPanel token={token} novelId={novelId} documentId={documentId} selectedText={selectedText} />
    </div>
  );
}
