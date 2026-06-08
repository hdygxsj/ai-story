import { Progress, Space, Tag, Typography } from "antd";

import type { ContextDetail } from "../../api/agent";

const SOURCE_LABELS: Record<string, string> = {
  user_instruction: "指令",
  selected_text: "选中文本",
  current_document: "当前文档",
  key_memory: "记忆",
  structured_memory: "素材",
  neighboring_chapter: "邻章",
  rag_result: "RAG",
  conversation_history: "历史",
};

type ContextStatusBarProps = {
  detail: ContextDetail | null;
};

export function ContextStatusBar({ detail }: ContextStatusBarProps) {
  if (!detail) {
    return null;
  }

  const percent = Math.min(100, Math.round(detail.usage_ratio * 100));
  const status = percent >= 85 ? "exception" : percent >= 70 ? "active" : "normal";

  return (
    <div
      aria-label="Agent 上下文状态"
      style={{
        background: "#f8fafc",
        border: "1px solid rgba(15,23,42,0.06)",
        borderRadius: 12,
        flexShrink: 0,
        padding: "10px 12px",
      }}
    >
      <Space direction="vertical" size={6} style={{ width: "100%" }}>
        <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
          <Typography.Text strong>上下文 {percent}%</Typography.Text>
          {detail.warnings.map((warning) => (
            <Tag color="orange" key={warning}>
              {warning}
            </Tag>
          ))}
        </Space>
        <Progress percent={percent} showInfo={false} size="small" status={status} />
        <Space size={[4, 4]} wrap>
          {detail.items.map((item) => (
            <Tag color={item.compressed ? "default" : "blue"} key={`${item.source}-${item.tokens}`}>
              {SOURCE_LABELS[item.source] ?? item.source}
              {item.compressed ? "（已压缩）" : ""}
            </Tag>
          ))}
        </Space>
      </Space>
    </div>
  );
}
