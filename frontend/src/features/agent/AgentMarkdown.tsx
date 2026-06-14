import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./agent-markdown.css";

type AgentMarkdownProps = {
  content: string;
};

const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="agent-markdown-table-wrap">
      <table>{children}</table>
    </div>
  ),
};

export function AgentMarkdown({ content }: AgentMarkdownProps) {
  if (!content.trim()) {
    return null;
  }

  return (
    <div className="agent-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
