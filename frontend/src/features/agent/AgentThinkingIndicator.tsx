import { LoadingOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

type AgentThinkingIndicatorProps = {
  content?: string;
  startedAt: number;
};

export function AgentThinkingIndicator({ content, startedAt }: AgentThinkingIndicatorProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const updateElapsed = () => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  const preview = content?.trim() ?? "";

  return (
    <div className="agent-thinking-indicator" data-testid="agent-thinking-indicator">
      <div className="agent-thinking-indicator-header">
        <LoadingOutlined className="agent-thinking-indicator-spinner" spin />
        <span className="agent-thinking-indicator-label">思考中</span>
        <span className="agent-thinking-indicator-time">{elapsedSeconds}s</span>
        <span aria-hidden="true" className="agent-thinking-indicator-dots">
          <span />
          <span />
          <span />
        </span>
      </div>
      {preview ? (
        <div className="agent-thinking-preview" title={preview}>
          {preview}
        </div>
      ) : null}
    </div>
  );
}
