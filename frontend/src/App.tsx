import { BookOutlined, DownOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { App as AntApp, Avatar, Button, ConfigProvider, Dropdown, Flex, Form, Input, Layout, Menu, Modal, Typography } from "antd";
import "antd/dist/reset.css";
import { useEffect, useState } from "react";

import type { Novel } from "./api/novels";
import { createNovel, exportNovel, listNovels } from "./api/novels";
import { AuthPage } from "./features/auth/AuthPage";
import { NovelList } from "./features/novels/NovelList";
import type { WorkspaceSection } from "./features/workspace/WorkspacePage";
import { WorkspacePage } from "./features/workspace/WorkspacePage";

const workspaceMenuItems: { key: WorkspaceSection; label: string }[] = [
  { key: "workspace", label: "工作台" },
  { key: "agent-config", label: "Agent配置" },
  { key: "memory", label: "记忆" },
  { key: "materials", label: "素材" },
];

export function App() {
  const [form] = Form.useForm<{ title: string }>();
  const [token, setToken] = useState<string | null>(null);
  const [novelId, setNovelId] = useState<string | null>(null);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [activeSection, setActiveSection] = useState<WorkspaceSection | "novels">("workspace");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creatingNovel, setCreatingNovel] = useState(false);

  useEffect(() => {
    if (!token) {
      setNovels([]);
      setNovelId(null);
      return;
    }

    let cancelled = false;

    async function loadNovels() {
      try {
        const loaded = await listNovels(token as string);
        if (!cancelled) {
          setNovels(loaded);
          setNovelId((current) => current ?? loaded[0]?.id ?? null);
          setActiveSection((current) => (current === "novels" ? current : "workspace"));
        }
      } catch {
        if (!cancelled) {
          setNovels([]);
        }
      }
    }

    void loadNovels();

    return () => {
      cancelled = true;
    };
  }, [token]);

  const selectedNovel = novels.find((novel) => novel.id === novelId) ?? null;

  async function handleCreateNovel(values: { title: string }) {
    if (!token) {
      return;
    }

    setCreatingNovel(true);
    try {
      const novel = await createNovel(token, values.title);
      setNovels((current) => [...current, novel]);
      setNovelId(novel.id);
      setActiveSection("workspace");
      setCreateModalOpen(false);
      form.resetFields();
    } finally {
      setCreatingNovel(false);
    }
  }

  function handleSelectNovel(nextNovelId: string) {
    setNovelId(nextNovelId);
    setActiveSection("workspace");
  }

  async function handleExportNovel() {
    if (!token || !selectedNovel) {
      return;
    }
    const blob = await exportNovel(token, selectedNovel.id, "markdown");
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedNovel.title}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          borderRadius: 14,
          colorPrimary: "#ff7a18",
          colorLink: "#fa541c",
        },
      }}
    >
      <AntApp>
        <Layout style={{ background: "linear-gradient(180deg, #fff7ed 0%, #f8fafc 42%, #f3f4f6 100%)", minHeight: "100vh" }}>
          <Layout.Header
            style={{
              alignItems: "center",
              background: "rgba(255,255,255,0.92)",
              backdropFilter: "blur(18px)",
              borderBottom: "1px solid rgba(255,122,24,0.14)",
              boxShadow: "0 12px 36px rgba(255,122,24,0.08)",
              display: "flex",
              gap: 18,
              height: 58,
              minWidth: 0,
              overflow: "hidden",
              paddingInline: 18,
              position: "sticky",
              top: 0,
              zIndex: 20,
            }}
          >
            <Flex align="center" gap={10} style={{ flex: "0 1 238px", minWidth: 150 }}>
              <Avatar
                icon={<BookOutlined />}
                shape="square"
                style={{ background: "linear-gradient(135deg, #ff7a18, #ff4d4f)", boxShadow: "0 10px 24px rgba(255,122,24,0.28)" }}
              />
              <div style={{ minWidth: 0 }}>
                <Typography.Title level={1} style={{ color: "#111827", fontSize: 16, lineHeight: 1.2, margin: 0 }}>
                  AI小说工坊
                </Typography.Title>
                <Typography.Text ellipsis style={{ color: "#6b7280", display: "block", fontSize: 12, maxWidth: 180 }}>
                  人机共创小说工作台
                </Typography.Text>
              </div>
            </Flex>
            {token && novelId ? (
              <Menu
                mode="horizontal"
                onClick={({ key }) => setActiveSection(key as WorkspaceSection)}
                selectedKeys={activeSection === "novels" ? [] : [activeSection]}
                items={workspaceMenuItems}
                style={{
                  background: "transparent",
                  borderBottom: "none",
                  flex: "1 1 auto",
                  justifyContent: "center",
                  minWidth: 0,
                }}
              />
            ) : null}
            {token ? (
              <Dropdown
                menu={{
                  items: [
                    ...novels.map((novel) => ({
                      key: `novel:${novel.id}`,
                      label: (
                        <Flex align="center" gap={10}>
                          <Avatar icon={<BookOutlined />} size="small" style={{ background: "#eef2ff", color: "#4f46e5" }} />
                          <div>
                            <div style={{ color: "#111827", fontWeight: 600 }}>{novel.title}</div>
                            <Typography.Text style={{ fontSize: 12 }} type="secondary">
                              小说工作区
                            </Typography.Text>
                          </div>
                        </Flex>
                      ),
                    })),
                    { type: "divider" as const },
                    { key: "export-md", label: "导出 Markdown" },
                    { key: "manage", icon: <SettingOutlined />, label: "管理小说" },
                    { key: "create", icon: <PlusOutlined />, label: "新建小说" },
                  ],
                  onClick: ({ key }) => {
                    if (key === "manage") {
                      setActiveSection("novels");
                      return;
                    }
                    if (key === "create") {
                      setCreateModalOpen(true);
                      return;
                    }
                    if (key === "export-md") {
                      void handleExportNovel();
                      return;
                    }
                    if (key.startsWith("novel:")) {
                      setNovelId(key.replace("novel:", ""));
                      setActiveSection("workspace");
                    }
                  },
                }}
                styles={{ root: { minWidth: 280 } }}
                trigger={["click"]}
              >
                <Button
                  aria-label={`小说切换器：${selectedNovel?.title ?? "未选择"}`}
                  style={{
                    background: "#ffffff",
                    border: "1px solid rgba(255,122,24,0.18)",
                    borderRadius: 999,
                    boxShadow: "0 10px 26px rgba(255,122,24,0.10)",
                    flexShrink: 1,
                    height: 42,
                    marginLeft: "auto",
                    maxWidth: 234,
                    minWidth: 0,
                    padding: "4px 12px 4px 6px",
                    width: "min(234px, 28vw)",
                  }}
                >
                  <Flex align="center" gap={10} justify="space-between">
                    <Flex align="center" gap={8} style={{ minWidth: 0 }}>
                      <Avatar icon={<BookOutlined />} size={28} style={{ background: "#fff7ed", color: "#ff7a18" }} />
                      <span style={{ color: "#111827", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {selectedNovel?.title ?? "未选择小说"}
                      </span>
                    </Flex>
                    <DownOutlined style={{ color: "#6b7280", fontSize: 12 }} />
                  </Flex>
                </Button>
              </Dropdown>
            ) : null}
          </Layout.Header>
          <Layout.Content
            style={{
              boxSizing: "border-box",
              display: "grid",
              height: "calc(100vh - 58px)",
              minHeight: 0,
              overflow: token && novelId && activeSection !== "novels" ? "hidden" : "auto",
              padding: token && novelId && activeSection !== "novels" ? 14 : "32px 24px",
              placeItems: token && novelId && activeSection !== "novels" ? "stretch" : "start center",
            }}
          >
            {!token ? <AuthPage onAuthenticated={setToken} /> : null}
            {token && (!novelId || activeSection === "novels") ? (
              <NovelList novels={novels} token={token} onNovelsChange={setNovels} onSelectNovel={handleSelectNovel} />
            ) : null}
            {token && novelId && activeSection !== "novels" ? (
              <WorkspacePage activeSection={activeSection} token={token} novelId={novelId} />
            ) : null}
          </Layout.Content>
        </Layout>
        <Modal
          confirmLoading={creatingNovel}
          okText="创建"
          onCancel={() => setCreateModalOpen(false)}
          onOk={() => form.submit()}
          open={createModalOpen}
          title="新建小说"
        >
          <Form form={form} initialValues={{ title: "新小说" }} layout="vertical" onFinish={handleCreateNovel}>
            <Form.Item label="小说标题" name="title" rules={[{ required: true, message: "请输入小说标题" }]}>
              <Input />
            </Form.Item>
          </Form>
        </Modal>
      </AntApp>
    </ConfigProvider>
  );
}
