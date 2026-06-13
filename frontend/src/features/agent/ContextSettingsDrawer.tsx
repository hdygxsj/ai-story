import { Drawer, Form, InputNumber, Space, Switch, Typography } from "antd";
import { useEffect, useState } from "react";

import type { ContextBudgetSettings, ContextSettings, ContextSources } from "../../api/conversations";
import { getContextSettings, updateContextSettings } from "../../api/conversations";

type ContextSettingsDrawerProps = {
  novelId: string;
  open: boolean;
  token: string;
  onClose: () => void;
};

const SOURCE_FIELDS: { key: keyof ContextSources; label: string }[] = [
  { key: "current_document", label: "当前文档" },
  { key: "selected_text", label: "选中文本" },
  { key: "key_memories", label: "关键记忆" },
  { key: "structured_assets", label: "结构化素材" },
  { key: "neighboring_chapters", label: "相邻章节" },
  { key: "rag_search", label: "RAG 检索" },
  { key: "conversation_history", label: "对话历史" },
];

export function ContextSettingsDrawer({ novelId, open, token, onClose }: ContextSettingsDrawerProps) {
  const [settings, setSettings] = useState<ContextSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    void getContextSettings(token, novelId)
      .then(setSettings)
      .catch(() => setSettings(null));
  }, [novelId, open, token]);

  async function handleSave() {
    if (!settings) {
      return;
    }
    setSaving(true);
    try {
      const updated = await updateContextSettings(token, novelId, {
        sources: settings.sources,
        budget: settings.budget,
      });
      setSettings(updated);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  function updateSource(key: keyof ContextSources, value: boolean) {
    setSettings((current) =>
      current ? { ...current, sources: { ...current.sources, [key]: value } } : current,
    );
  }

  function updateBudget(key: keyof ContextBudgetSettings, value: number | null) {
    if (value === null) {
      return;
    }
    setSettings((current) =>
      current ? { ...current, budget: { ...current.budget, [key]: value } } : current,
    );
  }

  return (
    <Drawer
      destroyOnClose
      open={open}
      title="上下文设置"
      width={360}
      onClose={onClose}
      footer={
        <Space>
          <Typography.Link onClick={onClose}>取消</Typography.Link>
          <Typography.Link disabled={saving || !settings} onClick={() => void handleSave()}>
            保存
          </Typography.Link>
        </Space>
      }
    >
      {settings ? (
        <Form layout="vertical">
          <Typography.Title level={5}>来源开关</Typography.Title>
          {SOURCE_FIELDS.map((field) => (
            <Form.Item key={field.key} label={field.label}>
              <Switch checked={settings.sources[field.key]} onChange={(checked) => updateSource(field.key, checked)} />
            </Form.Item>
          ))}
          <Typography.Title level={5} style={{ marginTop: 16 }}>
            预算
          </Typography.Title>
          <Form.Item label="最大上下文 Token">
            <InputNumber
              min={2000}
              style={{ width: "100%" }}
              value={settings.budget.max_context_tokens}
              onChange={(value) => updateBudget("max_context_tokens", value)}
            />
          </Form.Item>
          <Form.Item label="回复预留 Token">
            <InputNumber
              min={200}
              style={{ width: "100%" }}
              value={settings.budget.response_reserve}
              onChange={(value) => updateBudget("response_reserve", value)}
            />
          </Form.Item>
          <Form.Item label="相邻章节数">
            <InputNumber
              min={0}
              max={10}
              style={{ width: "100%" }}
              value={settings.budget.recent_chapters_count}
              onChange={(value) => updateBudget("recent_chapters_count", value)}
            />
          </Form.Item>
          <Form.Item label="对话历史上限">
            <InputNumber
              min={0}
              max={50}
              style={{ width: "100%" }}
              value={settings.budget.conversation_history_limit}
              onChange={(value) => updateBudget("conversation_history_limit", value)}
            />
          </Form.Item>
        </Form>
      ) : (
        <Typography.Text type="secondary">加载中…</Typography.Text>
      )}
    </Drawer>
  );
}
