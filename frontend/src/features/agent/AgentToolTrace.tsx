import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ToolOutlined } from "@ant-design/icons";
import { Collapse, Space, Typography } from "antd";

export type AgentToolCallRecord = {
  id: string;
  tool: string;
  status: "running" | "ok" | "error";
  args?: Record<string, unknown>;
  summary?: string | null;
};

export const DOCUMENT_WRITE_TOOLS = new Set([
  "create_chapter_with_content",
  "propose_document_update",
  "propose_rewrite",
  "propose_selection_replace",
  "propose_version_restore",
  "write_document_content",
]);

const TOOL_LABELS: Record<string, string> = {
  cleanup_workspace_folders: "清理目录",
  create_chapter_with_content: "写入章节",
  create_character_asset: "创建角色素材",
  create_timeline_event: "创建时间线事件",
  create_world_rule: "创建世界观规则",
  create_workspace_node: "创建工作区节点",
  list_creative_assets: "列出素材",
  list_document_versions: "列出文档版本",
  list_memory_items: "列出记忆",
  list_timeline_events: "列出时间线",
  list_workspace_nodes: "列出章节树",
  organize_workspace_tree: "整理章节树",
  propose_document_update: "更新正文（需确认）",
  propose_rewrite: "改写提案",
  propose_selection_replace: "替换选区",
  propose_version_restore: "恢复版本",
  read_document: "读取文档",
  restore_workspace_node: "恢复节点",
  save_key_memory: "保存记忆",
  search_memory: "检索记忆",
  search_rag: "检索上下文",
  split_chapter_by_max_chars: "拆分章节",
  trash_workspace_node: "移入回收站",
  update_character_state: "更新角色状态",
  update_novel: "重命名小说",
  update_workspace_node: "更新节点",
  write_document_content: "写入正文",
};

export function toolLabel(name: string) {
  return TOOL_LABELS[name] ?? name;
}

function statusIndicator(status: AgentToolCallRecord["status"]) {
  if (status === "running") {
    return (
      <span className="agent-tool-call-card-status is-running">
        <LoadingOutlined spin />
        执行中
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="agent-tool-call-card-status is-error">
        <CloseCircleOutlined />
        失败
      </span>
    );
  }
  return (
    <span className="agent-tool-call-card-status is-ok">
      <CheckCircleOutlined />
      完成
    </span>
  );
}

function compactDetail(toolCall: AgentToolCallRecord): string | null {
  const summary = toolCall.summary?.trim();
  if (summary && summary !== "执行成功") {
    return summary;
  }

  const args = toolCall.args;
  if (!args) {
    return null;
  }

  if (typeof args.title === "string" && args.title.trim()) {
    return args.title.trim();
  }
  if (typeof args.name === "string" && args.name.trim()) {
    return args.name.trim();
  }
  if (typeof args.content === "string" && args.content.trim()) {
    const content = args.content.trim();
    return content.length > 72 ? `${content.slice(0, 72)}…` : content;
  }
  if (typeof args.query === "string" && args.query.trim()) {
    return args.query.trim();
  }

  return null;
}

type AgentToolCallCardProps = {
  toolCall: AgentToolCallRecord;
};

export function AgentToolCallCard({ toolCall }: AgentToolCallCardProps) {
  const detail = compactDetail(toolCall);

  return (
    <div className="agent-tool-call-card" data-testid="agent-tool-call-card">
      <div className="agent-tool-call-card-header" data-testid={`agent-tool-${toolCall.id}`}>
        <ToolOutlined className="agent-tool-call-card-icon" />
        <span className="agent-tool-call-card-title">{toolLabel(toolCall.tool)}</span>
        {statusIndicator(toolCall.status)}
      </div>
      {detail ? <div className="agent-tool-call-card-detail">{detail}</div> : null}
    </div>
  );
}

type AgentToolTraceProps = {
  toolCalls: AgentToolCallRecord[];
};

export function AgentToolTrace({ toolCalls }: AgentToolTraceProps) {
  if (toolCalls.length === 0) {
    return null;
  }

  if (toolCalls.length === 1) {
    return <AgentToolCallCard toolCall={toolCalls[0]} />;
  }

  return (
    <div className="agent-tool-trace" data-testid="agent-tool-trace">
      <Collapse
        bordered={false}
        defaultActiveKey={["tools"]}
        items={[
          {
            key: "tools",
            label: (
              <Space size={6}>
                <ToolOutlined />
                <Typography.Text strong>工具调用 ({toolCalls.length})</Typography.Text>
              </Space>
            ),
            children: (
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                {toolCalls.map((item) => (
                  <AgentToolCallCard key={item.id} toolCall={item} />
                ))}
              </Space>
            ),
          },
        ]}
        size="small"
      />
    </div>
  );
}
