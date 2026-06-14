import { BookOutlined, DownOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { App as AntApp, Avatar, Badge, Button, ConfigProvider, Dropdown, Flex, Form, Input, Layout, Menu, Modal, Typography } from "antd";
import "antd/dist/reset.css";
import { useEffect, useState } from "react";

import { ApiError } from "./api/http";
import type { Novel } from "./api/novels";
import { createNovel, exportNovel, importNovel, listNovels } from "./api/novels";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { authRouteFromPath, pushAuthPath, type AuthRoute } from "./features/auth/authRoutes";
import { NovelList } from "./features/novels/NovelList";
import type { WorkspaceSection } from "./features/workspace/WorkspacePage";
import { WorkspacePage } from "./features/workspace/WorkspacePage";

const workspaceMenuItems: { key: WorkspaceSection; label: string }[] = [
  { key: "workspace", label: "工作台" },
  { key: "memory", label: "记忆" },
  { key: "confirmations", label: "确认" },
  { key: "materials", label: "素材" },
  { key: "timeline", label: "时间线" },
  { key: "agent-config", label: "Agent配置" },
];

const toolbarButtonBaseStyle = {
  alignItems: "center",
  borderRadius: 999,
  cursor: "pointer",
  display: "inline-flex",
  fontSize: 12,
  height: 30,
  justifyContent: "center",
  lineHeight: 1,
  padding: "0 12px",
  whiteSpace: "nowrap",
} as const;

const tokenStorageKey = "ai-story-token";
const novelStorageKey = "ai-story-novel-id";

const sectionPathByKey: Record<WorkspaceSection | "novels", string> = {
  "agent-config": "/agent-config",
  confirmations: "/confirmations",
  materials: "/materials",
  memory: "/memory",
  novels: "/novels",
  timeline: "/timeline",
  workspace: "/workspace",
};

function sectionFromPath(pathname: string): WorkspaceSection | "novels" {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/agent-config") {
    return "agent-config";
  }
  if (normalized === "/memory") {
    return "memory";
  }
  if (normalized === "/materials") {
    return "materials";
  }
  if (normalized === "/timeline") {
    return "timeline";
  }
  if (normalized === "/confirmations") {
    return "confirmations";
  }
  if (normalized === "/novels") {
    return "novels";
  }
  return "workspace";
}

function pushSectionPath(section: WorkspaceSection | "novels") {
  const nextPath = sectionPathByKey[section];
  if (window.location.pathname !== nextPath) {
    window.history.pushState(null, "", nextPath);
  }
}

export function App() {
  const [form] = Form.useForm<{ title: string }>();
  const [importForm] = Form.useForm<{ importTitle: string; content: string }>();
  const [token, setToken] = useState<string | null>(() => window.localStorage.getItem(tokenStorageKey));
  const [authRoute, setAuthRoute] = useState<AuthRoute>(() => authRouteFromPath(window.location.pathname));
  const [registerSuccessMessage, setRegisterSuccessMessage] = useState<string | null>(null);
  const [novelId, setNovelId] = useState<string | null>(null);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [activeSection, setActiveSection] = useState<WorkspaceSection | "novels">(() => sectionFromPath(window.location.pathname));
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creatingNovel, setCreatingNovel] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importingNovel, setImportingNovel] = useState(false);
  const [pendingConfirmationCount, setPendingConfirmationCount] = useState(0);

  useEffect(() => {
    function handlePopState() {
      if (!token) {
        setAuthRoute(authRouteFromPath(window.location.pathname));
        return;
      }
      setActiveSection(sectionFromPath(window.location.pathname));
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setNovels([]);
      setNovelId(null);
      window.localStorage.removeItem(tokenStorageKey);
      window.localStorage.removeItem(novelStorageKey);
      const route = authRouteFromPath(window.location.pathname);
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        pushAuthPath("login");
        setAuthRoute("login");
        return;
      }
      setAuthRoute(route);
      return;
    }
    window.localStorage.setItem(tokenStorageKey, token);

    let cancelled = false;

    async function loadNovels() {
      try {
        const loaded = await listNovels(token as string);
        if (!cancelled) {
          setNovels(loaded);
          setNovelId((current) => {
            const storedNovelId = window.localStorage.getItem(novelStorageKey);
            if (current && loaded.some((novel) => novel.id === current)) {
              return current;
            }
            if (storedNovelId && loaded.some((novel) => novel.id === storedNovelId)) {
              return storedNovelId;
            }
            return loaded[0]?.id ?? null;
          });
        }
      } catch (error) {
        if (!cancelled) {
          if (error instanceof ApiError && error.status === 401) {
            setToken(null);
            return;
          }
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

  useEffect(() => {
    if (novelId) {
      window.localStorage.setItem(novelStorageKey, novelId);
    }
  }, [novelId]);

  function handleAuthenticated(nextToken: string) {
    window.localStorage.setItem(tokenStorageKey, nextToken);
    setToken(nextToken);
    setRegisterSuccessMessage(null);
    if (
      window.location.pathname === "/" ||
      window.location.pathname === "/login" ||
      window.location.pathname === "/register"
    ) {
      pushSectionPath("workspace");
    }
  }

  function navigateToLogin() {
    setRegisterSuccessMessage(null);
    pushAuthPath("login");
    setAuthRoute("login");
  }

  function navigateToRegister() {
    setRegisterSuccessMessage(null);
    pushAuthPath("register");
    setAuthRoute("register");
  }

  function handleRegistered() {
    setRegisterSuccessMessage("注册成功，请使用邮箱或用户名登录");
    pushAuthPath("login");
    setAuthRoute("login");
  }

  function navigateSection(section: WorkspaceSection | "novels") {
    setActiveSection(section);
    pushSectionPath(section);
  }

  async function handleCreateNovel(values: { title: string }) {
    if (!token) {
      return;
    }

    setCreatingNovel(true);
    try {
      const novel = await createNovel(token, values.title);
      setNovels((current) => [...current, novel]);
      setNovelId(novel.id);
      navigateSection("workspace");
      setCreateModalOpen(false);
      form.resetFields();
    } finally {
      setCreatingNovel(false);
    }
  }

  function handleSelectNovel(nextNovelId: string) {
    setNovelId(nextNovelId);
    navigateSection("workspace");
  }

  async function handleExportNovel() {
    if (!token || !selectedNovel) {
      return;
    }
    const blob = await exportNovel(token, selectedNovel.id, "txt");
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedNovel.title}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleImportNovel(values: { importTitle: string; content: string }) {
    if (!token) {
      return;
    }

    setImportingNovel(true);
    try {
      const novel = await importNovel(token, {
        title: values.importTitle,
        content: values.content,
        format: "txt",
      });
      setNovels((current) => [...current, novel]);
      setNovelId(novel.id);
      navigateSection("workspace");
      setImportModalOpen(false);
      importForm.resetFields();
    } finally {
      setImportingNovel(false);
    }
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
                  执笔
                </Typography.Title>
                <Typography.Text ellipsis style={{ color: "#6b7280", display: "block", fontSize: 12, maxWidth: 180 }}>
                  人机共创小说工作台
                </Typography.Text>
              </div>
            </Flex>
            {token && novelId ? (
              <Menu
                mode="horizontal"
                onClick={({ key }) => navigateSection(key as WorkspaceSection)}
                selectedKeys={activeSection === "novels" ? [] : [activeSection]}
                items={workspaceMenuItems.map((item) =>
                  item.key === "confirmations"
                    ? {
                        ...item,
                        label: (
                          <span>
                            确认
                            {pendingConfirmationCount > 0 ? (
                              <Badge
                                count={pendingConfirmationCount}
                                size="small"
                                style={{ marginInlineStart: 8 }}
                              />
                            ) : null}
                          </span>
                        ),
                      }
                    : item,
                )}
                style={{
                  background: "transparent",
                  borderBottom: "none",
                  flex: "1 1 auto",
                  justifyContent: "center",
                  minWidth: 0,
                }}
              />
            ) : null}
            {token && novelId ? (
              <Flex gap={8} style={{ flexShrink: 0 }}>
                <button
                  aria-label="模型配置"
                  onClick={() => navigateSection("agent-config")}
                  style={{
                    ...toolbarButtonBaseStyle,
                    background: selectedNovel?.default_model_profile_id ? "#ffffff" : "#fff7ed",
                    border: selectedNovel?.default_model_profile_id
                      ? "1px solid rgba(255,122,24,0.18)"
                      : "1px solid rgba(255,122,24,0.42)",
                    color: selectedNovel?.default_model_profile_id ? "#374151" : "#c2410c",
                    fontWeight: selectedNovel?.default_model_profile_id ? 400 : 600,
                  }}
                  type="button"
                >
                  模型配置
                </button>
                <button
                  aria-label="导入小说"
                  onMouseDown={() => setImportModalOpen(true)}
                  onClick={() => setImportModalOpen(true)}
                  style={{
                    ...toolbarButtonBaseStyle,
                    background: "#fff7ed",
                    border: "1px solid rgba(255,122,24,0.28)",
                    color: "#c2410c",
                  }}
                  type="button"
                >
                  导入小说
                </button>
                <button
                  aria-label="导出 TXT"
                  onClick={() => void handleExportNovel()}
                  style={{
                    ...toolbarButtonBaseStyle,
                    background: "#ff7a18",
                    border: "1px solid #ff7a18",
                    color: "#ffffff",
                  }}
                  type="button"
                >
                  导出 TXT
                </button>
              </Flex>
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
                    { key: "export-txt", label: "导出 TXT" },
                    { key: "manage", icon: <SettingOutlined />, label: "管理小说" },
                    { key: "create", icon: <PlusOutlined />, label: "新建小说" },
                  ],
                  onClick: ({ key }) => {
                    if (key === "manage") {
                      navigateSection("novels");
                      return;
                    }
                    if (key === "create") {
                      setCreateModalOpen(true);
                      return;
                    }
                    if (key === "export-txt") {
                      void handleExportNovel();
                      return;
                    }
                    if (key.startsWith("novel:")) {
                      setNovelId(key.replace("novel:", ""));
                      navigateSection("workspace");
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
            {!token && authRoute === "login" ? (
              <LoginPage
                onAuthenticated={handleAuthenticated}
                onNavigateRegister={navigateToRegister}
                successMessage={registerSuccessMessage}
              />
            ) : null}
            {!token && authRoute === "register" ? (
              <RegisterPage onNavigateLogin={navigateToLogin} onRegistered={handleRegistered} />
            ) : null}
            {token && (!novelId || activeSection === "novels") ? (
              <NovelList novels={novels} token={token} onNovelsChange={setNovels} onSelectNovel={handleSelectNovel} />
            ) : null}
            {token && novelId && activeSection !== "novels" ? (
              <WorkspacePage
                activeSection={activeSection}
                defaultModelProfileId={selectedNovel?.default_model_profile_id ?? null}
                novelId={novelId}
                onActiveSectionChange={navigateSection}
                onOpenAgentConfig={() => navigateSection("agent-config")}
                onPendingConfirmationCountChange={setPendingConfirmationCount}
                onDefaultModelProfileChange={(profileId) => {
                  setNovels((current) =>
                    current.map((novel) =>
                      novel.id === novelId ? { ...novel, default_model_profile_id: profileId } : novel,
                    ),
                  );
                }}
                onNovelUpdated={(updated) => {
                  setNovels((current) =>
                    current.map((novel) =>
                      novel.id === updated.id
                        ? { ...novel, title: updated.title, description: updated.description }
                        : novel,
                    ),
                  );
                }}
                token={token}
              />
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
        <Modal
          confirmLoading={importingNovel}
          okText="导入"
          onCancel={() => setImportModalOpen(false)}
          onOk={() => importForm.submit()}
          open={importModalOpen}
          title="导入小说"
        >
          <Form form={importForm} layout="vertical" onFinish={handleImportNovel}>
            <Form.Item label="导入小说标题" name="importTitle" rules={[{ required: true, message: "请输入小说标题" }]}>
              <Input aria-label="导入小说标题" placeholder="例如：海灯记" />
            </Form.Item>
            <Form.Item label="导入正文" name="content" rules={[{ required: true, message: "请粘贴正文内容" }]}>
              <Input.TextArea aria-label="导入正文" autoSize={{ minRows: 8, maxRows: 14 }} placeholder="第一章&#10;正文内容..." />
            </Form.Item>
          </Form>
        </Modal>
      </AntApp>
    </ConfigProvider>
  );
}
