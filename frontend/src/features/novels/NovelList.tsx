import { Alert, Button, Card, Empty, Flex, Form, Input, List, Modal, Space, Typography } from "antd";
import { useEffect, useState } from "react";

import type { Novel } from "../../api/novels";
import { createNovel, importNovel, listNovels, updateNovel } from "../../api/novels";

type NovelListProps = {
  token: string;
  novels?: Novel[];
  onNovelsChange?: (novels: Novel[]) => void;
  onSelectNovel: (novelId: string) => void;
};

export function NovelList({ token, novels = [], onNovelsChange, onSelectNovel }: NovelListProps) {
  const [form] = Form.useForm<{ title: string }>();
  const [importForm] = Form.useForm<{ importTitle: string; content: string }>();
  const [localNovels, setLocalNovels] = useState<Novel[]>(novels);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renamingNovel, setRenamingNovel] = useState<Novel | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [renameForm] = Form.useForm<{ title: string }>();
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
          onNovelsChange?.(loaded);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "无法加载小说列表");
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
      const nextNovels = [...localNovels, novel];
      setLocalNovels(nextNovels);
      onNovelsChange?.(nextNovels);
      form.resetFields();
      onSelectNovel(novel.id);
    } finally {
      setCreating(false);
    }
  }

  async function handleImport(values: { importTitle: string; content: string }) {
    setImporting(true);
    try {
      const novel = await importNovel(token, { title: values.importTitle, content: values.content, format: "txt" });
      const nextNovels = [...localNovels, novel];
      setLocalNovels(nextNovels);
      onNovelsChange?.(nextNovels);
      importForm.resetFields();
      setImportOpen(false);
      onSelectNovel(novel.id);
    } finally {
      setImporting(false);
    }
  }

  function openRenameModal(novel: Novel) {
    setRenamingNovel(novel);
    renameForm.setFieldsValue({ title: novel.title });
    setRenameOpen(true);
  }

  async function handleRename(values: { title: string }) {
    if (!renamingNovel) {
      return;
    }
    setRenaming(true);
    try {
      const updated = await updateNovel(token, renamingNovel.id, { title: values.title });
      const nextNovels = localNovels.map((novel) => (novel.id === updated.id ? updated : novel));
      setLocalNovels(nextNovels);
      onNovelsChange?.(nextNovels);
      setRenameOpen(false);
      setRenamingNovel(null);
      renameForm.resetFields();
    } finally {
      setRenaming(false);
    }
  }

  return (
    <Card
      style={{
        border: "1px solid rgba(255,122,24,0.12)",
        borderRadius: 22,
        boxShadow: "0 18px 45px rgba(255,122,24,0.10)",
        width: "min(920px, 100%)",
      }}
    >
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
        <div>
          <Typography.Title level={2}>我的小说</Typography.Title>
          <Typography.Text type="secondary">创建或打开你的小说工作区。</Typography.Text>
        </div>
        <Flex gap={12} wrap="wrap">
          <Form form={form} initialValues={{ title: "新小说" }} layout="inline" onFinish={handleCreate}>
            <Form.Item name="title" rules={[{ required: true, message: "请输入小说标题" }]}>
              <Input aria-label="小说标题" placeholder="小说标题" />
            </Form.Item>
            <Button htmlType="submit" loading={creating} type="primary">
              创建小说
            </Button>
          </Form>
          <Button onClick={() => setImportOpen(true)}>导入小说</Button>
        </Flex>
        {error ? <Alert message={error} showIcon type="error" /> : null}
        {localNovels.length ? (
          <List
            dataSource={localNovels}
            loading={loading}
            renderItem={(novel) => (
              <List.Item
                actions={[
                  <Button key="rename" onClick={() => openRenameModal(novel)}>
                    重命名
                  </Button>,
                  <Button key="open" onClick={() => onSelectNovel(novel.id)}>
                    打开
                  </Button>,
                ]}
              >
                <List.Item.Meta description={novel.description || "暂无简介"} title={novel.title} />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="还没有小说，先创建一本开始写作。" />
        )}
      </Space>
      <Modal
        confirmLoading={importing}
        okText="导入"
        onCancel={() => setImportOpen(false)}
        onOk={() => importForm.submit()}
        open={importOpen}
        title="导入小说"
      >
        <Form form={importForm} layout="vertical" onFinish={handleImport}>
          <Form.Item label="导入小说标题" name="importTitle" rules={[{ required: true, message: "请输入小说标题" }]}>
            <Input aria-label="导入小说标题" placeholder="例如：海灯记" />
          </Form.Item>
          <Form.Item label="导入正文" name="content" rules={[{ required: true, message: "请粘贴正文内容" }]}>
            <Input.TextArea aria-label="导入正文" autoSize={{ minRows: 8, maxRows: 14 }} placeholder="第一章&#10;正文内容..." />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        confirmLoading={renaming}
        okText="保存"
        onCancel={() => {
          setRenameOpen(false);
          setRenamingNovel(null);
          renameForm.resetFields();
        }}
        onOk={() => renameForm.submit()}
        open={renameOpen}
        title="重命名小说"
      >
        <Form form={renameForm} layout="vertical" onFinish={handleRename}>
          <Form.Item label="小说标题" name="title" rules={[{ required: true, message: "请输入小说标题" }]}>
            <Input aria-label="重命名小说标题" placeholder="小说标题" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
