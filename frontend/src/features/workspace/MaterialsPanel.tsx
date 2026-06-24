import {
  BarChartOutlined,
  BookOutlined,
  CompassOutlined,
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  PlusOutlined,
  SearchOutlined,
  ShoppingOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Tabs, Tag, Timeline, Typography } from "antd";
import { useMemo, useState } from "react";

import type {
  CharacterAttribute,
  CharacterAttributePayload,
  CharacterState,
  CreativeAsset,
  InventoryItem,
  InventoryItemPayload,
  MapLocation,
  MapLocationPayload,
  MaterialChange,
  RelationshipEdge,
  TimelineEvent,
} from "../../api/materials";
import { dedupeCharacterStates } from "./characterStatePresentation";
import { RelationshipGraph } from "./RelationshipGraph";

import "./materials-panel.css";

type MaterialsPanelProps = {
  characterAttributes: CharacterAttribute[];
  creativeAssets: CreativeAsset[];
  characterStates: CharacterState[];
  inventoryItems: InventoryItem[];
  mapLocations: MapLocation[];
  relationshipEdges: RelationshipEdge[];
  timelineEvents: TimelineEvent[];
  materialChanges: MaterialChange[];
  onDeleteCharacterAttribute?: (attributeId: string) => Promise<void>;
  onDeleteCreativeAsset?: (assetId: string) => Promise<void>;
  onDeleteInventoryItem?: (itemId: string) => Promise<void>;
  onDeleteMapLocation?: (locationId: string) => Promise<void>;
  onUpsertCharacterAttribute?: (payload: CharacterAttributePayload) => Promise<void>;
  onUpsertInventoryItem?: (payload: InventoryItemPayload) => Promise<void>;
  onUpsertMapLocation?: (payload: MapLocationPayload) => Promise<void>;
  onUpdateCharacterAttribute?: (attributeId: string, payload: Partial<CharacterAttributePayload>) => Promise<void>;
  onUpdateCreativeAsset?: (
    assetId: string,
    payload: Pick<CreativeAsset, "asset_type" | "name" | "summary">,
  ) => Promise<void>;
  onUpdateInventoryItem?: (itemId: string, payload: Partial<InventoryItemPayload>) => Promise<void>;
  onUpdateMapLocation?: (locationId: string, payload: Partial<MapLocationPayload>) => Promise<void>;
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
  character_attribute: "人物属性",
  inventory_item: "背包",
  map_location: "地图",
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

function matchesMaterialSearch(query: string, ...parts: Array<string | undefined>) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return parts.some((part) => part?.toLowerCase().includes(normalized));
}

function formatStructuredValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function parseStructuredValue(raw: string) {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }
  const numeric = Number(trimmed);
  if (Number.isFinite(numeric) && trimmed !== "") {
    return numeric;
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function parseJsonObject(raw: string | undefined): Record<string, unknown> {
  const trimmed = raw?.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed) as unknown;
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
}

function parseNameList(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function MaterialItemId({ id }: { id: string }) {
  return (
    <Typography.Text className="materials-panel-item-id" copyable={{ text: id }} title={id}>
      {id}
    </Typography.Text>
  );
}

type CreativeAssetGridProps = {
  assets: CreativeAsset[];
  searchQuery: string;
  onDeleteCreativeAsset?: (assetId: string) => Promise<void>;
  onUpdateCreativeAsset?: (
    assetId: string,
    payload: Pick<CreativeAsset, "asset_type" | "name" | "summary">,
  ) => Promise<void>;
};

function CreativeAssetGrid({ assets, searchQuery, onDeleteCreativeAsset, onUpdateCreativeAsset }: CreativeAssetGridProps) {
  const [editingAsset, setEditingAsset] = useState<CreativeAsset | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<Pick<CreativeAsset, "asset_type" | "name" | "summary">>();
  const filteredAssets = useMemo(
    () =>
      assets.filter((asset) =>
        matchesMaterialSearch(searchQuery, asset.id, asset.name, asset.summary, asset.asset_type),
      ),
    [assets, searchQuery],
  );

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

  if (filteredAssets.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="没有匹配的创作资产，试试其他关键词或 ID"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <>
      <div className="materials-panel-grid">
        {filteredAssets.map((asset) => (
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
            <div className="materials-panel-item-footer">
              <div className="materials-panel-item-meta">
                <Tag className="materials-panel-type-tag" color={assetTypeColor(asset.asset_type)}>
                  {assetTypeLabel(asset.asset_type)}
                </Tag>
              </div>
              <MaterialItemId id={asset.id} />
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

function CharacterStateGrid({
  hiddenDuplicateCount = 0,
  states,
  searchQuery,
}: {
  hiddenDuplicateCount?: number;
  states: CharacterState[];
  searchQuery: string;
}) {
  const filteredStates = useMemo(
    () =>
      states.filter((state) =>
        matchesMaterialSearch(searchQuery, state.id, state.character_name, state.state, state.scope),
      ),
    [searchQuery, states],
  );

  if (states.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有角色状态记录，可以让 Agent 帮你追踪角色变化"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  if (filteredStates.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="没有匹配的角色状态，试试其他关键词或 ID"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <>
      {hiddenDuplicateCount > 0 ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="secondary">
          已合并 {hiddenDuplicateCount} 条重复角色状态，同一角色同一 scope 仅展示最新一条。
        </Typography.Text>
      ) : null}
      <div className="materials-panel-grid">
        {filteredStates.map((state) => (
        <article className="materials-panel-item" key={state.id}>
          <h4 className="materials-panel-item-title">{state.character_name}</h4>
          <p className="materials-panel-item-summary">{state.state}</p>
          <div className="materials-panel-item-footer">
            {state.scope ? (
              <div className="materials-panel-item-meta">
                <Tag className="materials-panel-type-tag" color="purple">
                  {state.scope}
                </Tag>
              </div>
            ) : (
              <span />
            )}
            <MaterialItemId id={state.id} />
          </div>
        </article>
      ))}
      </div>
    </>
  );
}

type CharacterAttributeFormValues = {
  attribute_key: string;
  character_name: string;
  scope?: string;
  unit?: string;
  value: string;
};

function CharacterAttributeGrid({
  attributes,
  onDeleteCharacterAttribute,
  onUpsertCharacterAttribute,
  onUpdateCharacterAttribute,
  searchQuery,
}: {
  attributes: CharacterAttribute[];
  onDeleteCharacterAttribute?: (attributeId: string) => Promise<void>;
  onUpsertCharacterAttribute?: (payload: CharacterAttributePayload) => Promise<void>;
  onUpdateCharacterAttribute?: (attributeId: string, payload: Partial<CharacterAttributePayload>) => Promise<void>;
  searchQuery: string;
}) {
  const [editingAttribute, setEditingAttribute] = useState<CharacterAttribute | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<CharacterAttributeFormValues>();
  const filteredAttributes = useMemo(
    () =>
      attributes.filter((attribute) =>
        matchesMaterialSearch(
          searchQuery,
          attribute.id,
          attribute.character_name,
          attribute.attribute_key,
          formatStructuredValue(attribute.value),
          attribute.scope,
        ),
      ),
    [attributes, searchQuery],
  );

  function openCreateModal() {
    setEditingAttribute(null);
    form.setFieldsValue({ scope: "current" });
    setModalOpen(true);
  }

  function openEditModal(attribute: CharacterAttribute) {
    setEditingAttribute(attribute);
    form.setFieldsValue({
      attribute_key: attribute.attribute_key,
      character_name: attribute.character_name,
      scope: attribute.scope ?? "current",
      unit: attribute.unit ?? "",
      value: formatStructuredValue(attribute.value),
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingAttribute(null);
    form.resetFields();
  }

  async function handleSave() {
    let values: CharacterAttributeFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    const payload: CharacterAttributePayload = {
      attribute_key: values.attribute_key,
      character_name: values.character_name,
      scope: values.scope || "current",
      unit: values.unit || "",
      value: parseStructuredValue(values.value),
    };
    setSaving(true);
    try {
      if (editingAttribute && onUpdateCharacterAttribute) {
        await onUpdateCharacterAttribute(editingAttribute.id, payload);
      } else if (onUpsertCharacterAttribute) {
        await onUpsertCharacterAttribute(payload);
      }
      closeModal();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="materials-panel-toolbar">
        {onUpsertCharacterAttribute ? (
          <Button icon={<PlusOutlined />} onClick={openCreateModal} type="primary">
            新增人物属性
          </Button>
        ) : null}
      </div>
      {attributes.length === 0 ? (
        <Empty className="materials-panel-empty" description="还没有人物属性记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : filteredAttributes.length === 0 ? (
        <Empty className="materials-panel-empty" description="没有匹配的人物属性" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="materials-panel-grid">
          {filteredAttributes.map((attribute) => (
            <article className="materials-panel-item" key={attribute.id}>
              <div className="materials-panel-item-header">
                <h4 className="materials-panel-item-title">{attribute.character_name}</h4>
                <div className="materials-panel-item-actions">
                  {onUpdateCharacterAttribute ? (
                    <Button aria-label={`编辑 ${attribute.character_name} ${attribute.attribute_key}`} icon={<EditOutlined />} onClick={() => openEditModal(attribute)} size="small" type="text" />
                  ) : null}
                  {onDeleteCharacterAttribute ? (
                    <Popconfirm cancelText="取消" okText="确认删除" onConfirm={() => void onDeleteCharacterAttribute(attribute.id)} title="删除这个人物属性？">
                      <Button aria-label={`删除 ${attribute.character_name} ${attribute.attribute_key}`} danger icon={<DeleteOutlined />} size="small" type="text" />
                    </Popconfirm>
                  ) : null}
                </div>
              </div>
              <p className="materials-panel-item-summary">
                <Typography.Text strong>{attribute.attribute_key}</Typography.Text>
                {"："}
                {formatStructuredValue(attribute.value)}
                {attribute.unit ? ` ${attribute.unit}` : ""}
              </p>
              <div className="materials-panel-item-footer">
                <div className="materials-panel-item-meta">
                  <Tag className="materials-panel-type-tag" color="geekblue">
                    {attribute.scope ?? "current"}
                  </Tag>
                </div>
                <MaterialItemId id={attribute.id} />
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal
        cancelText="取消"
        confirmLoading={saving}
        destroyOnHidden
        okText="保存"
        onCancel={closeModal}
        onOk={() => void handleSave()}
        open={modalOpen}
        title={editingAttribute ? "编辑人物属性" : "新增人物属性"}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="角色" name="character_name" rules={[{ required: true, message: "请输入角色" }]}>
            <Input maxLength={200} placeholder="角色名" />
          </Form.Item>
          <Form.Item label="属性" name="attribute_key" rules={[{ required: true, message: "请输入属性" }]}>
            <Input maxLength={120} placeholder="level / hp / location" />
          </Form.Item>
          <Form.Item label="数值" name="value" rules={[{ required: true, message: "请输入数值" }]}>
            <Input placeholder="数字、文本或 JSON" />
          </Form.Item>
          <Form.Item label="单位" name="unit">
            <Input maxLength={60} placeholder="级 / 点 / 枚" />
          </Form.Item>
          <Form.Item label="作用域" name="scope" initialValue="current">
            <Input maxLength={120} placeholder="current / chapter_3" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

type InventoryItemFormValues = {
  description?: string;
  item_name: string;
  location_name?: string;
  owner_name: string;
  quantity: number;
  unit?: string;
};

function InventoryItemGrid({
  items,
  onDeleteInventoryItem,
  onUpsertInventoryItem,
  onUpdateInventoryItem,
  searchQuery,
}: {
  items: InventoryItem[];
  onDeleteInventoryItem?: (itemId: string) => Promise<void>;
  onUpsertInventoryItem?: (payload: InventoryItemPayload) => Promise<void>;
  onUpdateInventoryItem?: (itemId: string, payload: Partial<InventoryItemPayload>) => Promise<void>;
  searchQuery: string;
}) {
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<InventoryItemFormValues>();
  const filteredItems = useMemo(
    () =>
      items.filter((item) =>
        matchesMaterialSearch(searchQuery, item.id, item.owner_name, item.item_name, item.location_name ?? undefined, item.description),
      ),
    [items, searchQuery],
  );

  function openCreateModal() {
    setEditingItem(null);
    setModalOpen(true);
  }

  function openEditModal(item: InventoryItem) {
    setEditingItem(item);
    form.setFieldsValue({
      description: item.description ?? "",
      item_name: item.item_name,
      location_name: item.location_name ?? "",
      owner_name: item.owner_name,
      quantity: item.quantity,
      unit: item.unit ?? "",
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingItem(null);
    form.resetFields();
  }

  async function handleSave() {
    let values: InventoryItemFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    const payload: InventoryItemPayload = {
      description: values.description ?? "",
      item_name: values.item_name,
      location_name: values.location_name || null,
      owner_name: values.owner_name,
      quantity: Number(values.quantity),
      unit: values.unit ?? "",
    };
    setSaving(true);
    try {
      if (editingItem && onUpdateInventoryItem) {
        await onUpdateInventoryItem(editingItem.id, payload);
      } else if (onUpsertInventoryItem) {
        await onUpsertInventoryItem(payload);
      }
      closeModal();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="materials-panel-toolbar">
        {onUpsertInventoryItem ? (
          <Button icon={<PlusOutlined />} onClick={openCreateModal} type="primary">
            新增背包物品
          </Button>
        ) : null}
      </div>
      {items.length === 0 ? (
        <Empty className="materials-panel-empty" description="还没有背包物品" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : filteredItems.length === 0 ? (
        <Empty className="materials-panel-empty" description="没有匹配的背包物品" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="materials-panel-grid">
          {filteredItems.map((item) => (
            <article className="materials-panel-item" key={item.id}>
              <div className="materials-panel-item-header">
                <h4 className="materials-panel-item-title">{item.item_name}</h4>
                <div className="materials-panel-item-actions">
                  {onUpdateInventoryItem ? <Button aria-label={`编辑 ${item.item_name}`} icon={<EditOutlined />} onClick={() => openEditModal(item)} size="small" type="text" /> : null}
                  {onDeleteInventoryItem ? (
                    <Popconfirm cancelText="取消" okText="确认删除" onConfirm={() => void onDeleteInventoryItem(item.id)} title="删除这个背包物品？">
                      <Button aria-label={`删除 ${item.item_name}`} danger icon={<DeleteOutlined />} size="small" type="text" />
                    </Popconfirm>
                  ) : null}
                </div>
              </div>
              <p className="materials-panel-item-summary">{item.description || "暂无描述"}</p>
              <div className="materials-panel-item-footer">
                <div className="materials-panel-item-meta">
                  <Tag color="gold">{item.owner_name}</Tag>
                  <Tag color="green">
                    {Number.isInteger(item.quantity) ? item.quantity.toFixed(0) : item.quantity} {item.unit}
                  </Tag>
                  {item.location_name ? <Tag color="blue">{item.location_name}</Tag> : null}
                </div>
                <MaterialItemId id={item.id} />
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal cancelText="取消" confirmLoading={saving} destroyOnHidden okText="保存" onCancel={closeModal} onOk={() => void handleSave()} open={modalOpen} title={editingItem ? "编辑背包物品" : "新增背包物品"}>
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="持有者" name="owner_name" rules={[{ required: true, message: "请输入持有者" }]}>
            <Input maxLength={200} placeholder="角色、势力或容器" />
          </Form.Item>
          <Form.Item label="物品" name="item_name" rules={[{ required: true, message: "请输入物品" }]}>
            <Input maxLength={200} placeholder="物品名" />
          </Form.Item>
          <Form.Item label="数量" name="quantity" rules={[{ required: true, message: "请输入数量" }]}>
            <Input type="number" />
          </Form.Item>
          <Form.Item label="单位" name="unit">
            <Input maxLength={60} placeholder="枚 / 件 / 瓶" />
          </Form.Item>
          <Form.Item label="位置" name="location_name">
            <Input maxLength={200} placeholder="存放地点" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

type MapLocationFormValues = {
  adjacent_location_names?: string;
  coordinates?: string;
  location_type?: string;
  name: string;
  parent_name?: string;
  summary: string;
};

function MapLocationGrid({
  locations,
  onDeleteMapLocation,
  onUpsertMapLocation,
  onUpdateMapLocation,
  searchQuery,
}: {
  locations: MapLocation[];
  onDeleteMapLocation?: (locationId: string) => Promise<void>;
  onUpsertMapLocation?: (payload: MapLocationPayload) => Promise<void>;
  onUpdateMapLocation?: (locationId: string, payload: Partial<MapLocationPayload>) => Promise<void>;
  searchQuery: string;
}) {
  const [editingLocation, setEditingLocation] = useState<MapLocation | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<MapLocationFormValues>();
  const filteredLocations = useMemo(
    () =>
      locations.filter((location) =>
        matchesMaterialSearch(searchQuery, location.id, location.name, location.location_type, location.summary, location.parent_name ?? undefined),
      ),
    [locations, searchQuery],
  );

  function openCreateModal() {
    setEditingLocation(null);
    form.setFieldsValue({ location_type: "location" });
    setModalOpen(true);
  }

  function openEditModal(location: MapLocation) {
    setEditingLocation(location);
    form.setFieldsValue({
      adjacent_location_names: (location.adjacent_location_names ?? []).join("，"),
      coordinates: JSON.stringify(location.coordinates ?? {}),
      location_type: location.location_type,
      name: location.name,
      parent_name: location.parent_name ?? "",
      summary: location.summary,
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingLocation(null);
    form.resetFields();
  }

  async function handleSave() {
    let values: MapLocationFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    const payload: MapLocationPayload = {
      adjacent_location_names: parseNameList(values.adjacent_location_names),
      coordinates: parseJsonObject(values.coordinates),
      location_type: values.location_type || "location",
      name: values.name,
      parent_name: values.parent_name || null,
      summary: values.summary,
    };
    setSaving(true);
    try {
      if (editingLocation && onUpdateMapLocation) {
        await onUpdateMapLocation(editingLocation.id, payload);
      } else if (onUpsertMapLocation) {
        await onUpsertMapLocation(payload);
      }
      closeModal();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="materials-panel-toolbar">
        {onUpsertMapLocation ? (
          <Button icon={<PlusOutlined />} onClick={openCreateModal} type="primary">
            新增地图地点
          </Button>
        ) : null}
      </div>
      {locations.length === 0 ? (
        <Empty className="materials-panel-empty" description="还没有地图地点" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : filteredLocations.length === 0 ? (
        <Empty className="materials-panel-empty" description="没有匹配的地图地点" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="materials-panel-grid">
          {filteredLocations.map((location) => (
            <article className="materials-panel-item" key={location.id}>
              <div className="materials-panel-item-header">
                <h4 className="materials-panel-item-title">{location.name}</h4>
                <div className="materials-panel-item-actions">
                  {onUpdateMapLocation ? <Button aria-label={`编辑 ${location.name}`} icon={<EditOutlined />} onClick={() => openEditModal(location)} size="small" type="text" /> : null}
                  {onDeleteMapLocation ? (
                    <Popconfirm cancelText="取消" okText="确认删除" onConfirm={() => void onDeleteMapLocation(location.id)} title="删除这个地图地点？">
                      <Button aria-label={`删除 ${location.name}`} danger icon={<DeleteOutlined />} size="small" type="text" />
                    </Popconfirm>
                  ) : null}
                </div>
              </div>
              <p className="materials-panel-item-summary">{location.summary}</p>
              <div className="materials-panel-item-footer">
                <div className="materials-panel-item-meta">
                  <Tag color="cyan">{location.location_type}</Tag>
                  {location.parent_name ? <Tag color="blue">{location.parent_name}</Tag> : null}
                  {location.coordinates ? <Tag color="purple">{Object.entries(location.coordinates).map(([key, value]) => `${key}: ${String(value)}`).join(", ")}</Tag> : null}
                </div>
                <MaterialItemId id={location.id} />
              </div>
            </article>
          ))}
        </div>
      )}
      <Modal cancelText="取消" confirmLoading={saving} destroyOnHidden okText="保存" onCancel={closeModal} onOk={() => void handleSave()} open={modalOpen} title={editingLocation ? "编辑地图地点" : "新增地图地点"}>
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
            <Input maxLength={200} placeholder="地点名" />
          </Form.Item>
          <Form.Item label="类型" name="location_type" initialValue="location">
            <Input maxLength={80} placeholder="town / region / dungeon" />
          </Form.Item>
          <Form.Item label="摘要" name="summary" rules={[{ required: true, message: "请输入摘要" }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item label="上级区域" name="parent_name">
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item label="坐标 JSON" name="coordinates">
            <Input placeholder='{"x":12,"y":-3}' />
          </Form.Item>
          <Form.Item label="相邻地点" name="adjacent_location_names">
            <Input placeholder="黑风岭，东荒渡口" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function RelationshipView({
  edges,
  searchQuery,
  timelineEvents,
}: {
  edges: RelationshipEdge[];
  searchQuery: string;
  timelineEvents: TimelineEvent[];
}) {
  const filteredEdges = useMemo(
    () =>
      edges.filter((edge) =>
        matchesMaterialSearch(
          searchQuery,
          edge.id,
          edge.source_character,
          edge.target_character,
          edge.relationship_type,
          edge.description,
        ),
      ),
    [edges, searchQuery],
  );

  if (edges.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有人物关系，可以让 Agent 帮你梳理角色之间的联系"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  if (filteredEdges.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="没有匹配的人物关系，试试其他关键词或 ID"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return <RelationshipGraph edges={filteredEdges} timelineEvents={timelineEvents} />;
}

function formatChangeTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function MaterialChangesView({ changes, searchQuery }: { changes: MaterialChange[]; searchQuery: string }) {
  const filteredChanges = useMemo(
    () =>
      changes.filter((change) =>
        matchesMaterialSearch(
          searchQuery,
          change.id,
          change.material_id,
          change.summary,
          change.material_type,
          change.action,
          change.actor_source,
        ),
      ),
    [changes, searchQuery],
  );

  if (changes.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="还没有素材变更记录"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  if (filteredChanges.length === 0) {
    return (
      <Empty
        className="materials-panel-empty"
        description="没有匹配的变更记录，试试其他关键词或 ID"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <Timeline
      className="materials-panel-changes"
      items={filteredChanges.map((change) => ({
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
              <MaterialItemId id={change.material_id} />
            </div>
          </article>
        ),
      }))}
    />
  );
}

export function MaterialsPanel({
  characterAttributes,
  creativeAssets,
  characterStates,
  inventoryItems,
  mapLocations,
  relationshipEdges,
  timelineEvents,
  materialChanges,
  onDeleteCharacterAttribute,
  onDeleteCreativeAsset,
  onDeleteInventoryItem,
  onDeleteMapLocation,
  onUpsertCharacterAttribute,
  onUpsertInventoryItem,
  onUpsertMapLocation,
  onUpdateCharacterAttribute,
  onUpdateCreativeAsset,
  onUpdateInventoryItem,
  onUpdateMapLocation,
}: MaterialsPanelProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const visibleCharacterStates = useMemo(() => dedupeCharacterStates(characterStates), [characterStates]);
  const hiddenCharacterStateCount = Math.max(0, characterStates.length - visibleCharacterStates.length);
  const totalCount =
    creativeAssets.length +
    visibleCharacterStates.length +
    characterAttributes.length +
    inventoryItems.length +
    mapLocations.length +
    relationshipEdges.length;

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
          管理结构化创作素材、角色状态、人物属性、背包、地图和人物关系，按类型浏览更清晰。
        </Typography.Paragraph>
        <div className="materials-panel-stats">
          <Tag color="orange">{totalCount} 项素材</Tag>
          <Tag color="gold">{creativeAssets.length} 创作资产</Tag>
          <Tag color="blue">{visibleCharacterStates.length} 角色状态</Tag>
          <Tag color="geekblue">{characterAttributes.length} 人物属性</Tag>
          <Tag color="green">{inventoryItems.length} 背包</Tag>
          <Tag color="cyan">{mapLocations.length} 地图</Tag>
          <Tag color="purple">{relationshipEdges.length} 人物关系</Tag>
          <Tag color="default">{materialChanges.length} 条变更</Tag>
        </div>
        <Input
          allowClear
          className="materials-panel-search"
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="按名称、内容或 ID 搜索当前标签页"
          prefix={<SearchOutlined />}
          value={searchQuery}
        />
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
                searchQuery={searchQuery}
              />
            ),
          },
          {
            key: "states",
            label: (
              <span>
                <UserOutlined /> 角色状态 ({visibleCharacterStates.length})
              </span>
            ),
            children: (
              <CharacterStateGrid
                hiddenDuplicateCount={hiddenCharacterStateCount}
                searchQuery={searchQuery}
                states={visibleCharacterStates}
              />
            ),
          },
          {
            key: "attributes",
            label: (
              <span>
                <BarChartOutlined /> 人物属性 ({characterAttributes.length})
              </span>
            ),
            children: (
              <CharacterAttributeGrid
                attributes={characterAttributes}
                onDeleteCharacterAttribute={onDeleteCharacterAttribute}
                onUpsertCharacterAttribute={onUpsertCharacterAttribute}
                onUpdateCharacterAttribute={onUpdateCharacterAttribute}
                searchQuery={searchQuery}
              />
            ),
          },
          {
            key: "inventory",
            label: (
              <span>
                <ShoppingOutlined /> 背包 ({inventoryItems.length})
              </span>
            ),
            children: (
              <InventoryItemGrid
                items={inventoryItems}
                onDeleteInventoryItem={onDeleteInventoryItem}
                onUpsertInventoryItem={onUpsertInventoryItem}
                onUpdateInventoryItem={onUpdateInventoryItem}
                searchQuery={searchQuery}
              />
            ),
          },
          {
            key: "map",
            label: (
              <span>
                <CompassOutlined /> 地图 ({mapLocations.length})
              </span>
            ),
            children: (
              <MapLocationGrid
                locations={mapLocations}
                onDeleteMapLocation={onDeleteMapLocation}
                onUpsertMapLocation={onUpsertMapLocation}
                onUpdateMapLocation={onUpdateMapLocation}
                searchQuery={searchQuery}
              />
            ),
          },
          {
            key: "relationships",
            label: (
              <span>
                <TeamOutlined /> 人物关系 ({relationshipEdges.length})
              </span>
            ),
            children: <RelationshipView edges={relationshipEdges} searchQuery={searchQuery} timelineEvents={timelineEvents} />,
          },
          {
            key: "changes",
            label: (
              <span>
                <HistoryOutlined /> 变更记录 ({materialChanges.length})
              </span>
            ),
            children: <MaterialChangesView changes={materialChanges} searchQuery={searchQuery} />,
          },
        ]}
      />
    </Card>
  );
}
