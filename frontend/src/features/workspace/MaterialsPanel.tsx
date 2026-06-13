import { BookOutlined, DeleteOutlined, EditOutlined, HistoryOutlined, TeamOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Tabs, Tag, Timeline, Typography } from "antd";
import { useState } from "react";

import type { CharacterState, CreativeAsset, MaterialChange, RelationshipEdge } from "../../api/materials";
import { RelationshipGraph } from "./RelationshipGraph";

import "./materials-panel.css";

type MaterialsPanelProps = {
  creativeAssets: CreativeAsset[];
  characterStates: CharacterState[];
  relationshipEdges: RelationshipEdge[];
  materialChanges: MaterialChange[];
  onDeleteCreativeAsset?: (assetId: string) => Promise<void>;
  onUpdateCreativeAsset?: (
    assetId: string,
    payload: Pick<CreativeAsset, "asset_type" | "name" | "summary">,
  ) => Promise<void>;
};

const assetTypeLabels: Record<string, string> = {
  character: "角色",
  world_rule: "世界观",
};

const assetTypeColors: Record<string, string> = {
  character: "orange",
  world_rule: "blue",
};

const assetTypeOptions = Object.entries(assetTypeLabels).map(([value, label]) => ({ value, label }));

const materialTypeLabels: Record<string, string> = {
  creative_asset: "创作资产",
  timeline_event: "时间线",
  character_state: "角色状态",
  relationship_edge: "人物关系",
};

const actionLabels: Record<string, string> = {
  created: "创建",
  updated: "更新",
  deleted: "删除",
};

const actorLabels: Record<string, string> = {
  user: "用户",
  agent: "Agent",
};

function assetTypeLabel(assetType: string) {
  return assetTypeLabels[assetType] ?? assetType;
}

function assetTypeColor(assetType: string) {
  return assetTypeColors[assetType] ?? "default";
}

type CreativeAssetGridProps = {
  assets: CreativeAsset[];
  onDeleteCreativeAsset?: (assetId: string) => Promise<void>;
  onUpdateCreativeAsset?: (
    assetId: string,
    payload: Pick<CreativeAsset, "asset_type" | "name" | "summary">,
  ) => Promise<void>;
};

function CreativeAssetGrid({ assets, onDeleteCreativeAsset, onUpdateCreativeAsset }: CreativeAssetGridProps) {
  const [editingAsset, setEditingAsset] = useState<CreativeAsset | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<Pick<CreativeAsset, "asset_type" | "name" | "summary">>();

  function openEditModal(asset: CreativeAsset) {
    setEditingAsset(asset);
    form.setFieldsValue({
      asset_type: asset.asset_type,
      name: asset.name,
      summary: asset.summary,
    });
  }

  function closeEditModal() {
    setEditingAsset(null);
    form.resetFields();
  }

  async function handleSave() {
    if (!editingAsset || !onUpdateCreativeAsset) {
      return;
    }
    let values: Pick<CreativeAsset, "asset_type" | "name" | "summary">;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    try {
      await onUpdateCreativeAsset(editingAsset.id, values);
      closeEditModal();
    } finally {
      setSaving(false);
    }
  }

  if (assets.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有创作资产，可以让 Agent 帮你创建角色、世界观等素材"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <>
      <div className="materials-panel-grid">
        {assets.map((asset) => (
          <article className="materials-panel-item" key={asset.id}>
            <div className="materials-panel-item-header">
              <h4 className="materials-panel-item-title">{asset.name}</h4>
              {onUpdateCreativeAsset || onDeleteCreativeAsset ? (
                <div className="materials-panel-item-actions">
                  {onUpdateCreativeAsset ? (
                    <Button
                      aria-label={`编辑 ${asset.name}`}
                      icon={<EditOutlined />}
                      onClick={() => openEditModal(asset)}
                      size="small"
                      type="text"
                    />
                  ) : null}
                  {onDeleteCreativeAsset ? (
                    <Popconfirm
                      cancelText="取消"
                      description="删除后，Agent 将无法再从素材库检索它。"
                      okText="确认删除"
                      onConfirm={() => void onDeleteCreativeAsset(asset.id)}
                      title="删除这个创作资产？"
                    >
                      <Button
                        aria-label={`删除 ${asset.name}`}
                        danger
                        icon={<DeleteOutlined />}
                        size="small"
                        type="text"
                      />
                    </Popconfirm>
                  ) : null}
                </div>
              ) : null}
            </div>
            <p className="materials-panel-item-summary">{asset.summary || "暂无摘要"}</p>
            <div className="materials-panel-item-meta">
              <Tag className="materials-panel-type-tag" color={assetTypeColor(asset.asset_type)}>
                {assetTypeLabel(asset.asset_type)}
              </Tag>
            </div>
          </article>
        ))}
      </div>

      <Modal
        cancelText="取消"
        confirmLoading={saving}
        destroyOnHidden
        okText="保存"
        onCancel={closeEditModal}
        onOk={() => void handleSave()}
        open={editingAsset !== null}
        title="编辑创作资产"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
            <Input maxLength={200} placeholder="资产名称" />
          </Form.Item>
          <Form.Item label="类型" name="asset_type" rules={[{ required: true, message: "请选择类型" }]}>
            <Select options={assetTypeOptions} placeholder="选择资产类型" />
          </Form.Item>
          <Form.Item label="摘要" name="summary" rules={[{ required: true, message: "请输入摘要" }]}>
            <Input.TextArea placeholder="描述这个创作资产" rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function CharacterStateGrid({ states }: { states: CharacterState[] }) {
  if (states.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有角色状态记录，可以让 Agent 帮你追踪角色变化"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <div className="materials-panel-grid">
      {states.map((state) => (
        <article className="materials-panel-item" key={state.id}>
          <h4 className="materials-panel-item-title">{state.character_name}</h4>
          <p className="materials-panel-item-summary">{state.state}</p>
          {state.scope ? (
            <div className="materials-panel-item-meta">
              <Tag className="materials-panel-type-tag" color="purple">
                {state.scope}
              </Tag>
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function RelationshipView({ edges }: { edges: RelationshipEdge[] }) {
  if (edges.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有人物关系，可以让 Agent 帮你梳理角色之间的联系"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return <RelationshipGraph edges={edges} />;
}

function formatChangeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function MaterialChangesView({ changes }: { changes: MaterialChange[] }) {
  if (changes.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有素材变更记录"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <Timeline
      className="materials-panel-changes"
      items={changes.map((change) => ({
        key: change.id,
        color: change.action === "deleted" ? "red" : change.action === "created" ? "green" : "blue",
        children: (
          <article className="materials-panel-change-item">
            <div className="materials-panel-change-header">
              <Typography.Text strong>{change.summary}</Typography.Text>
              <Typography.Text className="materials-panel-change-time" type="secondary">
                {formatChangeTime(change.created_at)}
              </Typography.Text>
            </div>
            <div className="materials-panel-item-meta">
              <Tag color="processing">{materialTypeLabels[change.material_type] ?? change.material_type}</Tag>
              <Tag>{actionLabels[change.action] ?? change.action}</Tag>
              <Tag color={change.actor_source === "agent" ? "purple" : "default"}>
                {actorLabels[change.actor_source] ?? change.actor_source}
              </Tag>
            </div>
          </article>
        ),
      }))}
    />
  );
}

export function MaterialsPanel({
  creativeAssets,
  characterStates,
  relationshipEdges,
  materialChanges,
  onDeleteCreativeAsset,
  onUpdateCreativeAsset,
}: MaterialsPanelProps) {
  const totalCount = creativeAssets.length + characterStates.length + relationshipEdges.length;

  return (
    <Card
      className="materials-panel-card"
      style={{
        border: "none",
        boxShadow: "0 18px 45px rgba(15, 23, 42, 0.08)",
        height: "100%",
        minWidth: 0,
      }}
      styles={{ body: { height: "100%", overflow: "hidden" } }}
    >
      <div className="materials-panel-header">
        <Typography.Title level={3}>素材</Typography.Title>
        <Typography.Paragraph type="secondary">
          管理结构化创作素材、角色状态和人物关系，按类型浏览更清晰。
        </Typography.Paragraph>
        <div className="materials-panel-stats">
          <Tag color="orange">{totalCount} 项素材</Tag>
          <Tag color="gold">{creativeAssets.length} 创作资产</Tag>
          <Tag color="blue">{characterStates.length} 角色状态</Tag>
          <Tag color="purple">{relationshipEdges.length} 人物关系</Tag>
          <Tag color="cyan">{materialChanges.length} 条变更</Tag>
        </div>
      </div>

      <Tabs
        className="materials-panel-tabs"
        destroyOnHidden={false}
        items={[
          {
            key: "assets",
            label: (
              <span>
                <BookOutlined /> 创作资产 ({creativeAssets.length})
              </span>
            ),
            children: (
              <CreativeAssetGrid
                assets={creativeAssets}
                onDeleteCreativeAsset={onDeleteCreativeAsset}
                onUpdateCreativeAsset={onUpdateCreativeAsset}
              />
            ),
          },
          {
            key: "states",
            label: (
              <span>
                <UserOutlined /> 角色状态 ({characterStates.length})
              </span>
            ),
            children: <CharacterStateGrid states={characterStates} />,
          },
          {
            key: "relationships",
            label: (
              <span>
                <TeamOutlined /> 人物关系 ({relationshipEdges.length})
              </span>
            ),
            children: <RelationshipView edges={relationshipEdges} />,
          },
          {
            key: "changes",
            label: (
              <span>
                <HistoryOutlined /> 变更记录 ({materialChanges.length})
              </span>
            ),
            children: <MaterialChangesView changes={materialChanges} />,
          },
        ]}
      />
    </Card>
  );
}
