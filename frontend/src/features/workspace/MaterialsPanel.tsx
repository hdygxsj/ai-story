import { BookOutlined, TeamOutlined, UserOutlined } from "@ant-design/icons";
import { Card, Empty, Tabs, Tag, Typography } from "antd";

import type { CharacterState, CreativeAsset, RelationshipEdge } from "../../api/materials";

import "./materials-panel.css";

type MaterialsPanelProps = {
  creativeAssets: CreativeAsset[];
  characterStates: CharacterState[];
  relationshipEdges: RelationshipEdge[];
};

const assetTypeLabels: Record<string, string> = {
  character: "角色",
  world_rule: "世界观",
};

const assetTypeColors: Record<string, string> = {
  character: "orange",
  world_rule: "blue",
};

function assetTypeLabel(assetType: string) {
  return assetTypeLabels[assetType] ?? assetType;
}

function assetTypeColor(assetType: string) {
  return assetTypeColors[assetType] ?? "default";
}

function CreativeAssetGrid({ assets }: { assets: CreativeAsset[] }) {
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
    <div className="materials-panel-grid">
      {assets.map((asset) => (
        <article className="materials-panel-item" key={asset.id}>
          <h4 className="materials-panel-item-title">{asset.name}</h4>
          <p className="materials-panel-item-summary">{asset.summary || "暂无摘要"}</p>
          <div className="materials-panel-item-meta">
            <Tag className="materials-panel-type-tag" color={assetTypeColor(asset.asset_type)}>
              {assetTypeLabel(asset.asset_type)}
            </Tag>
          </div>
        </article>
      ))}
    </div>
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

function RelationshipGrid({ edges }: { edges: RelationshipEdge[] }) {
  if (edges.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有人物关系，可以让 Agent 帮你梳理角色之间的联系"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <div className="materials-panel-grid">
      {edges.map((edge) => (
        <article className="materials-panel-item" key={edge.id}>
          <h4 className="materials-panel-item-title">{edge.relationship_type}</h4>
          <div className="materials-panel-relationship">
            <span className="materials-panel-relationship-node">{edge.source_character}</span>
            <span className="materials-panel-relationship-arrow">→</span>
            <span className="materials-panel-relationship-node">{edge.target_character}</span>
          </div>
          {edge.description ? <p className="materials-panel-item-summary">{edge.description}</p> : null}
        </article>
      ))}
    </div>
  );
}

export function MaterialsPanel({ creativeAssets, characterStates, relationshipEdges }: MaterialsPanelProps) {
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
            children: <CreativeAssetGrid assets={creativeAssets} />,
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
            children: <RelationshipGrid edges={relationshipEdges} />,
          },
        ]}
      />
    </Card>
  );
}
