import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

describe("WorkspacePage", () => {
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
      gridTemplateColumns: "260px 6px minmax(0, 1fr) clamp(300px, 28vw, 390px)",
      minHeight: "0",
      overflow: "hidden",
    });
    expect(screen.getByTestId("workspace-grid")).not.toHaveStyle({ height: "100%" });
  });

  it("resizes and persists the chapter tree panel width", () => {
    window.localStorage.setItem("ai-story-workspace-tree-width", "330");

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "330px 6px minmax(0, 1fr) clamp(300px, 28vw, 390px)",
    });

    fireEvent.mouseDown(screen.getByRole("separator", { name: "调整章节面板宽度" }), { clientX: 330 });
    fireEvent.mouseMove(window, { clientX: 390 });
    fireEvent.mouseUp(window);

    expect(window.localStorage.getItem("ai-story-workspace-tree-width")).toBe("390");
    expect(screen.getByTestId("workspace-grid")).toHaveStyle({
      gridTemplateColumns: "390px 6px minmax(0, 1fr) clamp(300px, 28vw, 390px)",
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
    expect(screen.getByLabelText("配置名称")).toBeInTheDocument();
    expect(screen.getByLabelText("供应商")).toBeInTheDocument();
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
    await user.click(screen.getByLabelText("向量场景供应商"));
    await user.click(await screen.findByText("Ollama 本地"));
    expect(screen.getByDisplayValue("nomic-embed-text")).toBeInTheDocument();

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

  it("shows selected editor text as an Agent quote card and sends it for rewrite", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/agent/messages")) {
        return Promise.resolve(jsonResponse({ message: "已创建改写确认。", context_status: [], confirmation: null }));
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "被选中的段落",
    } as Selection);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await user.click(screen.getByTestId("tiptap-editor"));
    fireEvent.mouseUp(screen.getByTestId("tiptap-editor"));
    fireEvent(document, new Event("selectionchange"));

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
        "http://localhost:8000/novels/novel-1/agent/messages",
        expect.objectContaining({
          body: expect.stringContaining("被选中的段落"),
        }),
      ),
    );
  });

  it("shows Agent workspace diff and refreshes nodes after directory organization", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
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
      if (url.endsWith("/novels/novel-1/agent/messages")) {
        return Promise.resolve(
          jsonResponse({
            message: "已整理章节、文件夹和草稿，并保存目录草稿。",
            context_status: [],
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
          }),
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
  });
});
