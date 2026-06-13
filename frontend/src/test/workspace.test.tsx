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
    expect(screen.getByRole("heading", { name: "共创 Agent" })).toBeInTheDocument();
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
    expect(screen.getByTestId("agent-panel-header")).toContainElement(screen.getByTestId("agent-conversation-sidebar"));
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
      if (url.endsWith("/documents/doc-1")) {
        return Promise.resolve(jsonResponse({ id: "doc-1", content: { type: "doc", content: [] } }));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

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
    await user.click((await screen.findByText("通 过")).closest("button") as HTMLButtonElement);

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
});
