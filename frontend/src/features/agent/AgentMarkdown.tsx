import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./agent-markdown.css";

type AgentMarkdownProps = {
  content: string;
};

export function AgentMarkdown({ content }: AgentMarkdownProps) {
  if (!content.trim()) {
    return null;
  }

  return (
    <div className="agent-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
