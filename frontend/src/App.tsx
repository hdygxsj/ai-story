import { App as AntApp, ConfigProvider, Layout, Typography } from "antd";
import "antd/dist/reset.css";
import { useState } from "react";

import { AuthPage } from "./features/auth/AuthPage";
import { NovelList } from "./features/novels/NovelList";
import { WorkspacePage } from "./features/workspace/WorkspacePage";

export function App() {
  const [token, setToken] = useState<string | null>(null);
  const [novelId, setNovelId] = useState<string | null>(null);

  return (
    <ConfigProvider
      theme={{
        token: {
          borderRadius: 10,
          colorPrimary: "#635bff",
        },
      }}
    >
      <AntApp>
        <Layout style={{ minHeight: "100vh" }}>
          <Layout.Header style={{ alignItems: "center", display: "flex", gap: 16 }}>
            <Typography.Title level={1} style={{ color: "white", margin: 0 }}>
              AI Story
            </Typography.Title>
            <Typography.Text style={{ color: "rgba(255,255,255,0.72)" }}>
              Agent-first novel creation IDE
            </Typography.Text>
          </Layout.Header>
          <Layout.Content style={{ display: "grid", minHeight: 0, placeItems: token && novelId ? "stretch" : "center", padding: 24 }}>
            {!token ? <AuthPage onAuthenticated={setToken} /> : null}
            {token && !novelId ? <NovelList token={token} onSelectNovel={setNovelId} /> : null}
            {token && novelId ? <WorkspacePage token={token} novelId={novelId} /> : null}
          </Layout.Content>
        </Layout>
      </AntApp>
    </ConfigProvider>
  );
}
