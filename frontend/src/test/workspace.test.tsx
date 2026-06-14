import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function conversationMockResponse(url: string) {
  if (url.endsWith("/novels/novel-1/conversations")) {
    return jsonResponse([]);
  }
  if (/\/novels\/novel-1\/conversations\/[^/]+\/messages$/.test(url)) {
    return jsonResponse([]);
  }
  return null;
}

async function waitForDocumentEditorReady() {
  await waitFor(() => {
    expect(screen.getByLabelText("章节名称")).not.toBeDisabled();
    expect(screen.queryByTestId("document-editor-loading")).not.toBeInTheDocument();
  });
}

function sseResponse(events: unknown[]) {
  const encoder = new TextEncoder();
  const payload = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(payload));
        controller.close();
      },
    }),
    {
      headers: { "Content-Type": "text/event-stream" },
      status: 200,
    },
  );
}

describe("WorkspacePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const conversationResponse = conversationMockResponse(url);
        if (conversationResponse) {
          return Promise.resolve(conversationResponse);
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the Chinese main workspace without content tabs", () => {
    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Agent" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "正文编辑器" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "执笔" })).toBeInTheDocument();
    expect(screen.getByTestId("tiptap-editor")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Document editor" })).not.toBeInTheDocument();
    expect(screen.getByTestId("workspace-shell")).toHaveStyle({
      height: "100%",
    });
    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "260px 6px minmax(0, 1fr) 6px 420px",
      gridTemplateRows: "minmax(0, 1fr)",
      height: "100%",
      minHeight: "0",
      overflow: "hidden",
    });
  });

  it("resizes and persists the chapter tree panel width", () => {
    window.localStorage.setItem("ai-story-workspace-tree-width", "330");

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "330px 6px minmax(0, 1fr) 6px 420px",
    });

    fireEvent.mouseDown(screen.getByRole("separator", { name: "调整章节面板宽度" }), { clientX: 330 });
    fireEvent.mouseMove(window, { clientX: 390 });
    fireEvent.mouseUp(window);

    expect(window.localStorage.getItem("ai-story-workspace-tree-width")).toBe("390");
    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "390px 6px minmax(0, 1fr) 6px 420px",
    });
  });

  it("collapses and restores the chapter tree while persisting visibility", async () => {
    const user = userEvent.setup();
    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await user.click(screen.getByRole("button", { name: "收起章节" }));

    expect(screen.queryByLabelText("章节树")).not.toBeInTheDocument();
    expect(screen.queryByRole("separator", { name: "调整章节面板宽度" })).not.toBeInTheDocument();
    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "minmax(0, 1fr) 6px 420px",
    });
    expect(window.localStorage.getItem("ai-story-workspace-tree-collapsed")).toBe("true");

    await user.click(screen.getByRole("button", { name: "展开章节" }));

    expect(screen.getByLabelText("章节树")).toBeInTheDocument();
    expect(window.localStorage.getItem("ai-story-workspace-tree-collapsed")).toBe("false");
  });

  it("restores the last selected chapter after refresh", async () => {
    window.localStorage.setItem("ai-story-workspace-last-document", JSON.stringify({ "novel-1": "doc-2" }));

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/novels/novel-1/nodes")) {
          return Promise.resolve(
            jsonResponse([
              { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
              { id: "node-2", title: "第二章", node_type: "chapter", parent_id: null, document_id: "doc-2", position: 1 },
            ]),
          );
        }
        if (url.endsWith("/documents/doc-2/versions")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/documents/doc-2")) {
          return Promise.resolve(
            jsonResponse({
              id: "doc-2",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "第二章内容" }] }],
              },
            }),
          );
        }
        const conversationResponse = conversationMockResponse(url);
        if (conversationResponse) {
          return Promise.resolve(conversationResponse);
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await waitForDocumentEditorReady();
    expect(await screen.findByLabelText("章节名称")).toHaveValue("第二章");
    expect(await screen.findByText("第二章内容")).toBeInTheDocument();
  });

  it("restores the last agent conversation after refresh", async () => {
    window.localStorage.setItem("ai-story-workspace-last-conversation", JSON.stringify({ "novel-1": "conv-2" }));

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/novels/novel-1/conversations")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "conv-1",
                novel_id: "novel-1",
                title: "对话一",
                created_at: "2026-06-14T00:00:00Z",
                updated_at: "2026-06-14T00:00:00Z",
              },
              {
                id: "conv-2",
                novel_id: "novel-1",
                title: "对话二",
                created_at: "2026-06-14T00:00:00Z",
                updated_at: "2026-06-14T00:00:00Z",
              },
            ]),
          );
        }
        if (url.endsWith("/novels/novel-1/conversations/conv-2/messages")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "msg-1",
                role: "user",
                content: "上次聊的内容",
                created_at: "2026-06-14T00:00:00Z",
              },
            ]),
          );
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("上次聊的内容")).toBeInTheDocument();
    });

    const messageScroll = screen.getByTestId("agent-message-scroll");
    expect(messageScroll.scrollTop).toBe(messageScroll.scrollHeight);
  });

  it("resizes and persists the Agent panel width", () => {
    window.localStorage.setItem("ai-story-agent-panel-width", "500");
    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "260px 6px minmax(0, 1fr) 6px 500px",
    });

    fireEvent.mouseDown(screen.getByRole("separator", { name: "调整 Agent 面板宽度" }), { clientX: 900 });
    fireEvent.mouseMove(window, { clientX: 700 });
    fireEvent.mouseUp(window);

    expect(window.localStorage.getItem("ai-story-agent-panel-width")).toBe("640");
    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "260px 6px minmax(0, 1fr) 6px 640px",
    });
  });

  it("shows compact novel statistics above the workspace columns", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/novels/novel-1/nodes")) {
          return Promise.resolve(
            jsonResponse([
              { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
              { id: "node-2", title: "资料夹", node_type: "folder", parent_id: null, document_id: null, position: 1 },
            ]),
          );
        }
        if (url.endsWith("/documents/doc-1")) {
          return Promise.resolve(
            jsonResponse({
              id: "doc-1",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "雾港灯塔" }] }],
              },
            }),
          );
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(await screen.findByText("作品概览")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-editor-column")).toContainElement(screen.getByTestId("workspace-overview"));
    expect(screen.getByTestId("agent-panel-header")).toBeInTheDocument();
    expect(screen.getByTestId("agent-conversation-sidebar")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("章节").length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(screen.getByText("当前字数")).toBeInTheDocument();
    expect(screen.getByText("已同步")).toBeInTheDocument();
    expect(screen.getByLabelText("章节名称")).toHaveValue("第一章");
  });

  it("renames the current chapter directly above the editor", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes") && init?.method !== "POST") {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({ id: "node-1", title: "第一章 新标题", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 }),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await waitForDocumentEditorReady();
    const titleInput = await screen.findByLabelText("章节名称");
    await user.clear(titleInput);
    await user.type(titleInput, "第一章 新标题{Enter}");

    await waitFor(() => {
      const renameCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH",
      );
      expect(renameCall).toBeTruthy();
      expect(String(renameCall?.[1]?.body)).toContain("\"title\":\"第一章 新标题\"");
    });
  });

  it("saves the current document with Ctrl+S or Cmd+S", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: JSON.parse(String(init.body)).content }));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "快捷保存内容" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await screen.findByText("快捷保存内容");
    const saveEvent = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ctrlKey: true, key: "s" });

    document.dispatchEvent(saveEvent);

    expect(saveEvent.defaultPrevented).toBe(true);
    await waitFor(() => {
      const saveCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/documents/doc-1") && init?.method === "PATCH");
      expect(saveCall).toBeTruthy();
    });
  });

  it("opens version history and restores a saved version", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1/versions/version-1/restore") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "历史正文内容" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "version-1",
              document_id: "doc-1",
              source: "user",
              created_at: "2026-06-14T10:00:00.000Z",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "历史正文内容" }] }],
              },
            },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "当前正文内容" }] }],
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await screen.findByText("当前正文内容");
    await user.click(screen.getByRole("button", { name: "版本历史" }));
    expect(await screen.findByText("历史正文内容")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "恢复" }));
    await waitFor(() => {
      const restoreCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/documents/doc-1/versions/version-1/restore") && init?.method === "POST",
      );
      expect(restoreCall).toBeTruthy();
    });
  });

  it("refreshes document versions after approving a confirmation", async () => {
    const user = userEvent.setup();
    let versionCalls = 0;
    let confirmationResolved = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/confirmations")) {
        return Promise.resolve(
          jsonResponse(
            confirmationResolved
              ? []
              : [{ id: "confirmation-1", action_type: "selection_replace", status: "pending", payload: { replacement_text: "新文本" } }],
          ),
        );
      }
      if (url.endsWith("/confirmations/confirmation-1/approve") && init?.method === "POST") {
        confirmationResolved = true;
        return Promise.resolve(
          jsonResponse({
            id: "confirmation-1",
            action_type: "selection_replace",
            status: "approved",
            payload: {},
            document_id: "doc-1",
          }),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        versionCalls += 1;
        return Promise.resolve(
          jsonResponse(
            versionCalls > 1
              ? [
                  { id: "version-2", document_id: "doc-1", source: "agent", content: {} },
                  { id: "version-1", document_id: "doc-1", source: "user", content: {} },
                ]
              : [{ id: "version-1", document_id: "doc-1", source: "user", content: {} }],
          ),
        );
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="confirmations" token="test-token" novelId="novel-1" />);
    const approveButtons = await screen.findAllByRole("button", { name: "写入正文" });
    await user.click(approveButtons[0]!);

    await waitFor(() => expect(versionCalls).toBeGreaterThan(1));
    expect(await screen.findByText("2 个已保存版本")).toBeInTheDocument();
  });

  it("commits the focused chapter title when saving with shortcut", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({ id: "node-1", title: "第一章 即时保存", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 }),
        );
      }
      if (url.endsWith("/documents/doc-1") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: JSON.parse(String(init.body)).content }));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await waitForDocumentEditorReady();
    const titleInput = await screen.findByLabelText("章节名称");
    await user.clear(titleInput);
    await user.type(titleInput, "第一章 即时保存");

    const saveEvent = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ctrlKey: true, key: "s" });
    document.dispatchEvent(saveEvent);

    expect(await screen.findByText("第一章 即时保存")).toBeInTheDocument();
    await waitFor(() => {
      const renameCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH",
      );
      expect(renameCall).toBeTruthy();
      expect(String(renameCall?.[1]?.body)).toContain("\"title\":\"第一章 即时保存\"");
    });
  });

  it("opens the Agent configuration tab for model profile setup", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            id: "profile-created",
            name: "多模型配置",
            provider_kind: "openai-compatible",
            chat_provider_kind: "anthropic",
            chat_model: "chat-model",
            writing_provider_kind: "openai-compatible",
            writing_model: "writing-model",
            summary_provider_kind: "openai",
            summary_model: "summary-model",
            embedding_provider_kind: "ollama",
            embedding_model: "nomic-embed-text",
          }),
        );
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/novels/novel-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            default_model_profile_id: "profile-created",
            description: "",
            id: "novel-1",
            title: "Novel",
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal(
      "fetch",
      fetchMock,
    );

    render(<WorkspacePage activeSection="agent-config" token="test-token" novelId="novel-1" />);

    expect(screen.getByRole("heading", { name: "Agent配置" })).toBeInTheDocument();
    expect(screen.getByTestId("agent-config-card")).toHaveStyle({ maxWidth: "960px" });
    expect(screen.getByText("当前还没有可用的模型配置")).toBeInTheDocument();
    expect(screen.getByTestId("model-tab-connectivity-default")).toBeInTheDocument();
    expect(screen.getByText("当前小说使用")).toBeInTheDocument();
    expect(screen.getByText("新建配置")).toBeInTheDocument();
    expect(screen.getByLabelText("配置名称")).toBeInTheDocument();
    expect(screen.queryByLabelText("供应商")).not.toBeInTheDocument();
    expect(screen.getByLabelText("默认供应商")).toBeInTheDocument();
    expect(screen.getByLabelText("默认对话模型")).toBeInTheDocument();
    expect(screen.getByLabelText("默认写作模型")).toBeInTheDocument();
    expect(screen.getByLabelText("默认总结模型")).toBeInTheDocument();
    expect(screen.queryByLabelText("默认向量模型")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "默认" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "对话" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "写作" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "总结" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "向量" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "对话" }));
    expect(screen.getByLabelText("对话场景供应商")).toBeInTheDocument();
    expect(screen.getByLabelText("对话 API Key")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "写作" }));
    expect(screen.getByLabelText("写作场景供应商")).toBeInTheDocument();
    expect(screen.getByLabelText("写作 API Key")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "总结" }));
    expect(screen.getByLabelText("总结场景供应商")).toBeInTheDocument();
    expect(screen.getByLabelText("总结 API Key")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "向量" }));
    expect(screen.getByLabelText("向量场景供应商")).toBeInTheDocument();
    expect(screen.getByLabelText("向量 API Key")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("配置名称"));
    await user.type(screen.getByLabelText("配置名称"), "多模型配置");
    await user.click(screen.getByRole("tab", { name: "默认" }));
    await user.type(screen.getByLabelText("默认 API Key"), "sk-default");
    await user.click(screen.getByRole("tab", { name: "对话" }));
    await user.click(screen.getByLabelText("对话场景供应商"));
    await user.click((await screen.findAllByText("Anthropic")).at(-1) as HTMLElement);
    await user.clear(screen.getByLabelText("对话 API Key"));
    await user.type(screen.getByLabelText("对话 API Key"), "sk-chat");
    await user.click(screen.getByRole("tab", { name: "写作" }));
    await user.clear(screen.getByLabelText("写作 API Key"));
    await user.type(screen.getByLabelText("写作 API Key"), "sk-writing");
    await user.click(screen.getByRole("tab", { name: "总结" }));
    await user.clear(screen.getByLabelText("总结 API Key"));
    await user.type(screen.getByLabelText("总结 API Key"), "sk-summary");
    await user.click(screen.getByRole("tab", { name: "向量" }));
    await user.click(screen.getByLabelText("向量场景供应商"));
    await user.click(await screen.findByText("Ollama 本地"));
    expect(screen.getByLabelText("向量模型")).toHaveValue("nomic-embed-text");
    await user.clear(screen.getByLabelText("向量 API Key"));
    await user.click(screen.getByRole("button", { name: "保存 Agent 配置" }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/model-profiles") && init?.method === "POST");
      expect(createCall).toBeTruthy();
      const body = String(createCall?.[1]?.body);
      expect(body).toContain("\"chat_provider_kind\":\"anthropic\"");
      expect(body).toContain("\"embedding_provider_kind\":\"ollama\"");
      expect(body).toContain("\"embedding_model\":\"nomic-embed-text\"");
      expect(body).toContain("\"embedding_base_url\":\"http://ollama:11434\"");
      expect(body).toContain("sk-writing");
    });
    await waitFor(() => {
      const updateNovelCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1") && init?.method === "PATCH",
      );
      expect(updateNovelCall).toBeTruthy();
      expect(String(updateNovelCall?.[1]?.body)).toContain("\"default_model_profile_id\":\"profile-created\"");
    });
  });

  it("tests model profile connectivity from the Agent configuration form", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles/test-connectivity") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            results: [
              { purpose: "chat", label: "对话", ok: true, message: "连通正常", model: "gpt-4o" },
              { purpose: "writing", label: "写作", ok: true, message: "连通正常", model: "gpt-4o" },
              { purpose: "summary", label: "总结", ok: false, message: "401 Unauthorized", model: "gpt-4o-mini" },
              { purpose: "embedding", label: "向量", ok: true, message: "连通正常，向量维度 1536", model: "text-embedding-3-small" },
            ],
          }),
        );
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="agent-config" token="test-token" novelId="novel-1" />);
    expect(screen.getByTestId("model-tab-connectivity-default")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "默认" }));
    await user.type(screen.getByLabelText("默认 API Key"), "sk-default");
    await user.click(within(screen.getByTestId("model-tab-connectivity-default")).getByRole("button", { name: "测试连通性" }));

    await waitFor(() => {
      const testCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/model-profiles/test-connectivity") && init?.method === "POST",
      );
      expect(testCall).toBeTruthy();
      const body = String(testCall?.[1]?.body);
      expect(body).toContain("sk-default");
      expect(body).toContain("\"purposes\":[\"chat\",\"writing\",\"summary\"]");
    });
    expect(await screen.findByText("401 Unauthorized")).toBeInTheDocument();
    expect(screen.getByTestId("model-tab-connectivity-default")).toBeInTheDocument();
  });

  it("tests only the chat model from the chat tab", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles/test-connectivity") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            results: [{ purpose: "chat", label: "对话", ok: true, message: "连通正常", model: "gpt-4o" }],
          }),
        );
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="agent-config" token="test-token" novelId="novel-1" />);
    await user.click(screen.getByRole("tab", { name: "默认" }));
    await user.type(screen.getByLabelText("默认 API Key"), "sk-default");
    await user.click(screen.getByRole("tab", { name: "对话" }));
    await user.click(within(screen.getByTestId("model-tab-connectivity-chat")).getByRole("button", { name: "测试连通性" }));

    await waitFor(() => {
      const testCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/model-profiles/test-connectivity") && init?.method === "POST",
      );
      expect(testCall).toBeTruthy();
      expect(String(testCall?.[1]?.body)).toContain("\"purposes\":[\"chat\"]");
    });
    expect(await screen.findByText("连通正常")).toBeInTheDocument();
  });

  it("restores the active model profile into the form on load", async () => {
    const existingProfile = {
      id: "profile-existing",
      name: "DeepSeek 配置",
      provider_kind: "openai-compatible",
      base_url: "https://api.deepseek.com",
      chat_provider_kind: "openai-compatible",
      chat_model: "deepseek-v4-pro",
      writing_provider_kind: "openai-compatible",
      writing_model: "deepseek-v4-pro",
      summary_provider_kind: "openai-compatible",
      summary_model: "deepseek-v4-pro",
      embedding_provider_kind: "openai",
      embedding_model: "text-embedding-3-small",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/model-profiles")) {
          return Promise.resolve(jsonResponse([existingProfile]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(
      <WorkspacePage
        activeSection="agent-config"
        defaultModelProfileId="profile-existing"
        token="test-token"
        novelId="novel-1"
      />,
    );

    expect(await screen.findByDisplayValue("DeepSeek 配置")).toBeInTheDocument();
    expect(screen.getByLabelText("默认对话模型")).toHaveValue("deepseek-v4-pro");
    expect(screen.getByLabelText("默认写作模型")).toHaveValue("deepseek-v4-pro");
    expect(screen.getByLabelText("默认总结模型")).toHaveValue("deepseek-v4-pro");
    expect(screen.getByDisplayValue("https://api.deepseek.com")).toBeInTheDocument();
    expect(screen.getByText("编辑配置")).toBeInTheDocument();
  });

  it("keeps ollama embedding settings when saving from the default tab", async () => {
    const user = userEvent.setup();
    const existingProfile = {
      id: "profile-existing",
      name: "默认 OpenAI",
      provider_kind: "openai-compatible",
      base_url: "https://api.deepseek.com",
      chat_model: "deepseek-v4-pro",
      writing_model: "deepseek-v4-pro",
      summary_model: "deepseek-v4-pro",
      embedding_provider_kind: "ollama",
      embedding_model: "nomic-embed-text",
      embedding_base_url: "http://ollama:11434",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles/profile-existing") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse(existingProfile));
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse([existingProfile]));
      }
      if (url.endsWith("/novels/novel-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            default_model_profile_id: "profile-existing",
            description: "",
            id: "novel-1",
            title: "Novel",
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <WorkspacePage
        activeSection="agent-config"
        defaultModelProfileId="profile-existing"
        token="test-token"
        novelId="novel-1"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "编辑" }));
    await user.click(screen.getByRole("tab", { name: "默认" }));
    await user.click(screen.getByRole("button", { name: "保存 Agent 配置" }));

    await waitFor(() => {
      const updateCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/model-profiles/profile-existing") && init?.method === "PATCH",
      );
      expect(updateCall).toBeTruthy();
      const body = String(updateCall?.[1]?.body);
      expect(body).not.toContain("\"embedding_provider_kind\":null");
      expect(body).not.toContain("\"embedding_provider_kind\": null");
    });
  });

  it("updates an existing model profile from the configured list", async () => {
    const user = userEvent.setup();
    const existingProfile = {
      id: "profile-existing",
      name: "默认 OpenAI",
      provider_kind: "openai",
      chat_provider_kind: "openai",
      chat_model: "gpt-4o",
      writing_provider_kind: "openai",
      writing_model: "gpt-4o",
      summary_provider_kind: "openai",
      summary_model: "gpt-4o-mini",
      embedding_provider_kind: "openai",
      embedding_model: "text-embedding-3-small",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles/profile-existing") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            ...existingProfile,
            embedding_provider_kind: "ollama",
            embedding_model: "nomic-embed-text",
            embedding_base_url: "http://ollama:11434",
          }),
        );
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse([existingProfile]));
      }
      if (url.endsWith("/novels/novel-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            default_model_profile_id: "profile-existing",
            description: "",
            id: "novel-1",
            title: "Novel",
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <WorkspacePage
        activeSection="agent-config"
        defaultModelProfileId="profile-existing"
        token="test-token"
        novelId="novel-1"
      />,
    );

    expect(await screen.findByRole("button", { name: "编辑" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "编辑" }));
    expect(screen.getByText("编辑配置")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "向量" }));
    await user.click(screen.getByLabelText("向量场景供应商"));
    await user.click(await screen.findByText("Ollama 本地"));
    await user.click(screen.getByRole("button", { name: "保存 Agent 配置" }));

    await waitFor(() => {
      const updateCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/model-profiles/profile-existing") && init?.method === "PATCH",
      );
      expect(updateCall).toBeTruthy();
      expect(String(updateCall?.[1]?.body)).toContain("\"embedding_provider_kind\":\"ollama\"");
      expect(String(updateCall?.[1]?.body)).not.toContain("api_key");
    });
  });

  it("switches and deletes model profiles from the configured list", async () => {
    const user = userEvent.setup();
    const profiles = [
      {
        id: "profile-a",
        name: "默认 OpenAI",
        provider_kind: "openai",
        chat_model: "gpt-4o",
        writing_model: "gpt-4o",
        summary_model: "gpt-4o-mini",
        embedding_provider_kind: "ollama",
        embedding_model: "nomic-embed-text",
      },
      {
        id: "profile-b",
        name: "DeepSeek",
        provider_kind: "openai-compatible",
        chat_model: "deepseek-v4-pro",
        writing_model: "deepseek-v4-pro",
        summary_model: "deepseek-v4-pro",
        embedding_provider_kind: "ollama",
        embedding_model: "nomic-embed-text",
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/model-profiles/profile-a") && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/model-profiles")) {
        return Promise.resolve(jsonResponse(profiles));
      }
      if (url.endsWith("/novels/novel-1") && init?.method === "PATCH") {
        return Promise.resolve(
          jsonResponse({
            default_model_profile_id: JSON.parse(String(init.body)).default_model_profile_id ?? null,
            description: "",
            id: "novel-1",
            title: "Novel",
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <WorkspacePage
        activeSection="agent-config"
        defaultModelProfileId="profile-b"
        onDefaultModelProfileChange={vi.fn()}
        token="test-token"
        novelId="novel-1"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "设为当前" }));
    await waitFor(() => {
      const switchCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1") && init?.method === "PATCH",
      );
      expect(switchCall).toBeTruthy();
      expect(String(switchCall?.[1]?.body)).toContain("\"default_model_profile_id\":\"profile-a\"");
    });

    await user.click(screen.getAllByRole("button", { name: "删除" })[0]);
    const popconfirm = await screen.findByText("确定删除「默认 OpenAI」吗？");
    const popover = popconfirm.closest(".ant-popover") as HTMLElement;
    await user.click(within(popover).getByRole("button", { name: /^删/ }));

    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(
        ([url, init]) => String(url).endsWith("/model-profiles/profile-a") && init?.method === "DELETE",
      );
      expect(deleteCall).toBeTruthy();
    });
  });

  it("shows selected editor text as an Agent quote card and sends it for rewrite", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "已创建改写确认。" },
            {
              type: "done",
              message: "已创建改写确认。",
              context_status: [],
              conversation_id: "conv-1",
              confirmation: null,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "getSelection").mockReturnValue({
      rangeCount: 1,
      getRangeAt: () => ({ getBoundingClientRect: () => ({ bottom: 120, left: 180 }) }),
      toString: () => "被选中的段落",
    } as unknown as Selection);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await user.click(screen.getByTestId("tiptap-editor"));
    fireEvent.mouseUp(screen.getByTestId("tiptap-editor"));
    fireEvent(document, new Event("selectionchange"));

    expect(await screen.findByLabelText("选中文本操作")).toBeInTheDocument();
    expect(screen.getByLabelText("选中文本操作")).toHaveStyle({
      left: "180px",
      position: "fixed",
      top: "128px",
    });
    expect(screen.queryByText("已引用选中段落")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "引用" }));
    expect(await screen.findByText("已引用选中段落")).toBeInTheDocument();
    expect(screen.getByText("被选中的段落")).toBeInTheDocument();
    expect(screen.getByTestId("agent-message-scroll")).toHaveStyle({
      flex: "1 1 0",
      minHeight: "0",
      overflow: "auto",
    });
    expect(screen.getByTestId("agent-input-shell")).toHaveStyle({ flexShrink: "0" });
    expect(screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "改写引用" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/novels/novel-1/agent/messages/stream",
        expect.objectContaining({
          body: expect.stringContaining("被选中的段落"),
        }),
      ),
    );
  });

  it("shows Agent workspace diff and refreshes nodes after directory organization", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "folder-1", title: "草稿", node_type: "folder", parent_id: null, document_id: null, position: 0, status: "draft" },
            { id: "node-1", title: "草稿片段", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 1, status: "draft" },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "已整理章节、文件夹和草稿，并保存目录草稿。" },
            {
              type: "done",
              message: "已整理章节、文件夹和草稿，并保存目录草稿。",
              context_status: [],
              conversation_id: "conv-organize",
              confirmation: null,
              workspace_diff: {
                summary: "Agent 已整理章节目录",
                before: [
                  { id: "folder-1", title: "草稿", parent_id: null, position: 0, status: "draft" },
                  { id: "node-1", title: "草稿片段", parent_id: null, position: 1, status: "draft" },
                ],
                after: [
                  { id: "folder-1", title: "草稿", parent_id: null, position: 0, status: "draft" },
                  { id: "node-1", title: "草稿片段", parent_id: "folder-1", position: 0, status: "draft" },
                ],
                changes: [
                  {
                    action: "move",
                    node_id: "node-1",
                    title: "草稿片段",
                    before_parent_id: null,
                    after_parent_id: "folder-1",
                    before_position: 1,
                    after_position: 0,
                  },
                ],
              },
              workspace_nodes: [
                { id: "folder-1", title: "草稿", node_type: "folder", parent_id: null, document_id: null, position: 0, status: "draft" },
                { id: "node-1", title: "草稿片段", node_type: "chapter", parent_id: "folder-1", document_id: "doc-1", position: 0, status: "draft" },
              ],
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await user.clear(screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"));
    await user.type(screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"), "帮我整理章节和草稿目录{Enter}");

    expect(await screen.findByText("Agent 已整理章节目录")).toBeInTheDocument();
    expect(screen.getByText("移动：草稿片段")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "撤销本次整理" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "关闭目录变更提示" }));
    expect(screen.queryByText("Agent 已整理章节目录")).not.toBeInTheDocument();
  });

  it("refreshes creative collections after an Agent run", async () => {
    const user = userEvent.setup();
    let assetLoads = 0;
    let timelineLoads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/creative-assets")) {
        assetLoads += 1;
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/novels/novel-1/timeline-events")) {
        timelineLoads += 1;
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "已创建素材。" },
            {
              type: "done",
              message: "已创建素材。",
              context_status: [],
              conversation_id: "conv-material",
              confirmation: null,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await waitFor(() => expect(assetLoads).toBe(1));
    await waitFor(() => expect(timelineLoads).toBe(1));

    await user.type(
      screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"),
      "创建角色素材{Enter}",
    );

    await waitFor(() => expect(assetLoads).toBe(2));
    await waitFor(() => expect(timelineLoads).toBe(2));
  });

  it("opens a chapter created by the Agent", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/documents/doc-created/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-created")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-created",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "第一章已经写入工作台" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "第一章已写入工作台。" },
            {
              type: "done",
              message: "第一章已写入工作台。",
              context_status: [],
              conversation_id: "conv-write",
              confirmation: null,
              workspace_nodes: [
                {
                  id: "node-created",
                  novel_id: "novel-1",
                  title: "第一章",
                  node_type: "chapter",
                  parent_id: null,
                  document_id: "doc-created",
                  position: 0,
                  status: "draft",
                },
              ],
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await user.type(
      screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"),
      "写完第一章并放进工作台{Enter}",
    );

    expect(await screen.findByText("第一章已经写入工作台")).toBeInTheDocument();
    expect(screen.getByText("第一章")).toBeInTheDocument();
  });

  it("shows inline confirmation to write generated body into the current document", async () => {
    const user = userEvent.setup();
    let approved = false;
    let confirmationCreated = false;
    const pendingConfirmation = {
      id: "confirmation-write",
      action_type: "document_update",
      status: "pending",
      payload: { content: "Agent 已写入正文" },
      document_id: "doc-1",
      before_text: "旧正文",
      after_text: "Agent 已写入正文",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: approved ? "Agent 已写入正文" : "旧正文" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/confirmations/confirmation-write/approve") && init?.method === "POST") {
        approved = true;
        return Promise.resolve(
          jsonResponse({
            id: "confirmation-write",
            action_type: "document_update",
            status: "approved",
            payload: { content: "Agent 已写入正文" },
            document_id: "doc-1",
          }),
        );
      }
      if (url.endsWith("/novels/novel-1/confirmations")) {
        return Promise.resolve(
          jsonResponse(confirmationCreated && !approved ? [pendingConfirmation] : []),
        );
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        confirmationCreated = true;
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "已生成正文更新方案。" },
            {
              type: "done",
              message: "已生成正文更新方案。",
              context_status: [],
              conversation_id: "conv-write-body",
              confirmation: pendingConfirmation,
              workspace_nodes: null,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    expect(await screen.findByText("旧正文")).toBeInTheDocument();
    await user.type(
      screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"),
      "把这段正文写进当前章节{Enter}",
    );

    expect(await screen.findByTestId("agent-write-confirmation")).toBeInTheDocument();
    expect(await screen.findByTestId("confirmation-diff-view")).toBeInTheDocument();
    expect(screen.getByTestId("confirmation-diff-modify")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "写入正文" }));
    expect(await screen.findByText("Agent 已写入正文")).toBeInTheDocument();
  });

  it("shows pending confirmations in the chapter editor after workspace load", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "旧正文" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/novels/novel-1/confirmations")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "confirmation-pending",
              action_type: "document_update",
              status: "pending",
              payload: { content: "等待确认的新正文" },
              document_id: "doc-1",
              before_text: "旧正文",
              after_text: "等待确认的新正文",
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(await screen.findByTestId("agent-write-confirmation")).toBeInTheDocument();
    expect(screen.getByText("等待确认的新正文")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-node-pending-write-node-1")).toBeInTheDocument();
    expect(screen.queryByText("等待写入确认")).not.toBeInTheDocument();
  });

  it("does not show stale confirmations after the API auto-expires them", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(
          jsonResponse({
            id: "doc-1",
            content: {
              type: "doc",
              content: [{ type: "paragraph", content: [{ type: "text", text: "旧正文" }] }],
            },
          }),
        );
      }
      if (url.endsWith("/novels/novel-1/confirmations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await screen.findByText("旧正文");
    expect(screen.queryByTestId("agent-write-confirmation")).not.toBeInTheDocument();
  });

  it("shows tool call records in the Agent dialog", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        return Promise.resolve(
          sseResponse([
            {
              type: "tool_call",
              id: "run-1",
              tool: "create_chapter_with_content",
              status: "running",
              args: { title: "第一章", content: "正文内容" },
              summary: null,
            },
            {
              type: "tool_call",
              id: "run-1",
              tool: "create_chapter_with_content",
              status: "ok",
              args: { title: "第一章", content: "正文内容" },
              summary: "已将《第一章》写入工作台。",
            },
            { type: "delta", content: "第一章已写入。" },
            {
              type: "done",
              message: "第一章已写入。",
              context_status: [],
              conversation_id: "conv-tools",
              confirmation: null,
              tool_calls: [
                {
                  id: "run-1",
                  tool: "create_chapter_with_content",
                  status: "ok",
                  args: { title: "第一章", content: "正文内容" },
                  summary: "已将《第一章》写入工作台。",
                },
              ],
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await user.type(
      screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"),
      "写完第一章{Enter}",
    );

    expect(await screen.findByTestId("agent-tool-call-card")).toBeInTheDocument();
    expect(screen.getByText("写入章节")).toBeInTheDocument();
    expect(screen.getByText("已将《第一章》写入工作台。")).toBeInTheDocument();
  });
});
