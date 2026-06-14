import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ToolOutlined } from "@ant-design/icons";
import { Collapse, Space, Tag, Typography } from "antd";

export type AgentToolCallRecord = {
  id: string;
  tool: string;
  status: "running" | "ok" | "error";
  args?: Record<string, unknown>;
  summary?: string | null;
};

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

function toolLabel(name: string) {
  return TOOL_LABELS[name] ?? name;
}

function statusTag(status: AgentToolCallRecord["status"]) {
  if (status === "running") {
    return (
      <Tag color="processing" icon={<LoadingOutlined spin />}>
        执行中
      </Tag>
    );
  }
  if (status === "error") {
    return (
      <Tag color="error" icon={<CloseCircleOutlined />}>
        失败
      </Tag>
    );
  }
  return (
    <Tag color="success" icon={<CheckCircleOutlined />}>
      完成
    </Tag>
  );
}

function formatArgs(args: Record<string, unknown> | undefined) {
  if (!args || Object.keys(args).length === 0) {
    return null;
  }
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join("\n");
}

type AgentToolTraceProps = {
  toolCalls: AgentToolCallRecord[];
};

export function AgentToolTrace({ toolCalls }: AgentToolTraceProps) {
  if (toolCalls.length === 0) {
    return null;
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
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {toolCalls.map((item) => {
                  const argsText = formatArgs(item.args);
                  return (
                    <div className="agent-tool-trace-item" data-testid={`agent-tool-${item.id}`} key={item.id}>
                      <Space align="start" style={{ justifyContent: "space-between", width: "100%" }}>
                        <Typography.Text strong>{toolLabel(item.tool)}</Typography.Text>
                        {statusTag(item.status)}
                      </Space>
                      {item.summary ? (
                        <Typography.Paragraph style={{ marginBottom: argsText ? 4 : 0, whiteSpace: "pre-wrap" }} type="secondary">
                          {item.summary}
                        </Typography.Paragraph>
                      ) : null}
                      {argsText ? (
                        <Typography.Paragraph
                          code
                          style={{ fontSize: 12, marginBottom: 0, whiteSpace: "pre-wrap" }}
                          type="secondary"
                        >
                          {argsText}
                        </Typography.Paragraph>
                      ) : null}
                    </div>
                  );
                })}
              </Space>
            ),
          },
        ]}
        size="small"
      />
    </div>
  );
}
