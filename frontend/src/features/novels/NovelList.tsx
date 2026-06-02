import { Alert, Button, Card, Empty, Form, Input, List, Space, Typography } from "antd";
import { useEffect, useState } from "react";

import type { Novel } from "../../api/novels";
import { createNovel, listNovels } from "../../api/novels";

type NovelListProps = {
  token: string;
  novels?: Novel[];
  onSelectNovel: (novelId: string) => void;
};

export function NovelList({ token, novels = [], onSelectNovel }: NovelListProps) {
  const [form] = Form.useForm<{ title: string }>();
  const [localNovels, setLocalNovels] = useState<Novel[]>(novels);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadNovels() {
      setLoading(true);
      setError(null);
      try {
        const loaded = await listNovels(token);
        if (!cancelled) {
          setLocalNovels(loaded);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Unable to load novels");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadNovels();

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleCreate(values: { title: string }) {
    setCreating(true);
    try {
      const novel = await createNovel(token, values.title);
      setLocalNovels((current) => [...current, novel]);
      form.resetFields();
      onSelectNovel(novel.id);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Card style={{ width: "min(860px, 100%)" }}>
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
        <div>
          <Typography.Title level={2}>Novels</Typography.Title>
          <Typography.Text type="secondary">Create or open a user-owned novel workspace.</Typography.Text>
        </div>
        <Form form={form} initialValues={{ title: "New Novel" }} layout="inline" onFinish={handleCreate}>
          <Form.Item name="title" rules={[{ required: true, message: "Novel title is required" }]}>
            <Input aria-label="Novel title" placeholder="Novel title" />
          </Form.Item>
          <Button htmlType="submit" loading={creating} type="primary">
            Create Novel
          </Button>
        </Form>
        {error ? <Alert message={error} showIcon type="error" /> : null}
        {localNovels.length ? (
          <List
            dataSource={localNovels}
            loading={loading}
            renderItem={(novel) => (
              <List.Item actions={[<Button onClick={() => onSelectNovel(novel.id)}>Open</Button>]}>
                <List.Item.Meta description={novel.description || "No description yet"} title={novel.title} />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="No novels yet. Create one to start writing." />
        )}
      </Space>
    </Card>
  );
}
