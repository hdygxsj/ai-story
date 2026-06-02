import { useState } from "react";

import { AuthPage } from "./features/auth/AuthPage";
import { NovelList } from "./features/novels/NovelList";
import { WorkspacePage } from "./features/workspace/WorkspacePage";

export function App() {
  const [token, setToken] = useState<string | null>(null);
  const [novelId, setNovelId] = useState<string | null>(null);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
      <h1>AI Story</h1>
      <p>Agent-first novel creation IDE</p>
      {!token ? <AuthPage onAuthenticated={setToken} /> : null}
      {token && !novelId ? <NovelList token={token} onSelectNovel={setNovelId} /> : null}
      {token && novelId ? <WorkspacePage token={token} novelId={novelId} /> : null}
    </main>
  );
}
