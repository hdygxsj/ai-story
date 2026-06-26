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

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
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

async function waitForDocumentEditorReady(expectedTitle?: string, expectedContent?: string) {
  await waitFor(() => {
    const titleInput = screen.getByLabelText("章节名称");
    expect(titleInput).not.toBeDisabled();
    expect(screen.queryByTestId("document-editor-loading")).not.toBeInTheDocument();
    if (expectedTitle) {
      expect(titleInput).toHaveValue(expectedTitle);
    }
    if (expectedContent) {
      expect(screen.getByText(expectedContent)).toBeInTheDocument();
    }
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

  it("loads structured story state collections for materials", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="materials" token="test-token" novelId="novel-1" />);

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) => requestUrl(input));
      expect(urls.some((url) => url.endsWith("/novels/novel-1/character-attributes"))).toBe(true);
      expect(urls.some((url) => url.endsWith("/novels/novel-1/inventory-items"))).toBe(true);
      expect(urls.some((url) => url.endsWith("/novels/novel-1/map-locations"))).toBe(true);
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
        const url = requestUrl(input);
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

    await waitForDocumentEditorReady("第二章");
    expect(await screen.findByText("第二章内容")).toBeInTheDocument();
  });

  it("resets the editor scroll position when switching chapters", async () => {
    const user = userEvent.setup();
    let resolveSecondChapter: ((response: Response) => void) | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.endsWith("/novels/novel-1/nodes")) {
          return Promise.resolve(
            jsonResponse([
              { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
              { id: "node-2", title: "第二章", node_type: "chapter", parent_id: null, document_id: "doc-2", position: 1 },
            ]),
          );
        }
        if (url.endsWith("/documents/doc-1/versions") || url.endsWith("/documents/doc-2/versions")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/documents/doc-1")) {
          return Promise.resolve(
            jsonResponse({
              id: "doc-1",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "第一章内容" }] }],
              },
            }),
          );
        }
        if (url.endsWith("/documents/doc-2")) {
          return new Promise<Response>((resolve) => {
            resolveSecondChapter = resolve;
          });
        }
        const conversationResponse = conversationMockResponse(url);
        if (conversationResponse) {
          return Promise.resolve(conversationResponse);
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await waitForDocumentEditorReady("第一章", "第一章内容");

    const editorBody = screen.getByTestId("workspace-chapter-panel").querySelector(".ant-card-body") as HTMLElement;
    editorBody.scrollTop = 640;
    await user.click(await screen.findByTestId("workspace-node-title-node-2"));
    await waitFor(() => expect(resolveSecondChapter).toBeTruthy());
    editorBody.scrollTop = 640;
    resolveSecondChapter?.(
      jsonResponse({
        id: "doc-2",
        content: {
          type: "doc",
          content: [{ type: "paragraph", content: [{ type: "text", text: "第二章内容" }] }],
        },
      }),
    );

    await waitForDocumentEditorReady("第二章", "第二章内容");
    await waitFor(() => expect(editorBody.scrollTop).toBe(0));
  });

  it("scrolls the document editor to the top and bottom from header buttons", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = requestUrl(input);
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
                content: [{ type: "paragraph", content: [{ type: "text", text: "第一章内容" }] }],
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
    await waitForDocumentEditorReady("第一章", "第一章内容");

    const editorBody = screen.getByTestId("workspace-chapter-panel").querySelector(".ant-card-body") as HTMLElement;
    Object.defineProperty(editorBody, "scrollHeight", { configurable: true, value: 1800 });
    editorBody.scrollTop = 420;

    await user.click(screen.getByRole("button", { name: "回到正文顶部" }));
    expect(editorBody.scrollTop).toBe(0);

    await user.click(screen.getByRole("button", { name: "跳到正文底部" }));
    expect(editorBody.scrollTop).toBe(1800);
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

  it("continues the same agent conversation after the first streamed reply", async () => {
    const user = userEvent.setup();
    const requestBodies: unknown[] = [];
    let streamCount = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/agent/messages/stream")) {
        requestBodies.push(JSON.parse(String(init?.body)));
        streamCount += 1;
        return Promise.resolve(
          sseResponse([
            { type: "meta", conversation_id: "conv-continuing" },
            {
              type: "delta",
              content: streamCount === 1 ? "上一轮已处理。" : "继续处理。",
            },
            {
              type: "done",
              message: streamCount === 1 ? "上一轮已处理。" : "继续处理。",
              context_status: [],
              conversation_id: "conv-continuing",
              confirmation: null,
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    const input = screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文");
    await user.type(input, "先改第38章");
    await user.keyboard("{Enter}");
    await screen.findByText("上一轮已处理。");

    await user.type(input, "第40章和第49章也同步修改");
    await user.keyboard("{Enter}");
    await screen.findByText("继续处理。");

    expect(requestBodies).toHaveLength(2);
    expect(requestBodies[0]).toMatchObject({ conversation_id: null });
    expect(requestBodies[1]).toMatchObject({ conversation_id: "conv-continuing" });
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
        if (url.endsWith("/documents/doc-1/versions")) {
          return Promise.resolve(jsonResponse([]));
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

  it("copies a local Agent setup prompt from the Agent panel header", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    await user.click(screen.getByRole("button", { name: "复制本地 Agent 接入提示" }));

    expect(writeText).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("/local-agent-skill/SKILL.md");
    expect(copied).toContain("AI_STORY_ACCESS_TOKEN=test-token");
    expect(copied).toContain("ai-story agent manifest");
    expect(copied).toContain("ai-story tools run");
    expect(await screen.findByText("已复制本地 Agent 接入提示")).toBeInTheDocument();
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

    await waitForDocumentEditorReady("第一章");
    const titleInput = screen.getByLabelText("章节名称");
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
      if (url.endsWith("/documents/doc-1/versions")) {
        return Promise.resolve(jsonResponse([]));
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

  it("compares a saved version with the current document in version history", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
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
                content: [
                  { type: "paragraph", content: [{ type: "text", text: "共同开头" }] },
                  { type: "paragraph", content: [{ type: "text", text: "旧中段" }] },
                  { type: "paragraph", content: [{ type: "text", text: "共同结尾" }] },
                ],
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
              content: [
                { type: "paragraph", content: [{ type: "text", text: "共同开头" }] },
                { type: "paragraph", content: [{ type: "text", text: "新中段" }] },
                { type: "paragraph", content: [{ type: "text", text: "共同结尾" }] },
              ],
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await screen.findByText("新中段");
    await user.click(screen.getByRole("button", { name: "版本历史" }));
    await user.click(await screen.findByRole("button", { name: "对比当前" }));

    expect(await screen.findByText("版本对比")).toBeInTheDocument();
    const dialog = screen.getByTestId("version-diff-modal");
    expect(within(dialog).getByText("历史版本")).toBeInTheDocument();
    expect(within(dialog).getByText("当前正文")).toBeInTheDocument();
    expect(screen.queryByTestId("confirmation-diff-view")).not.toBeInTheDocument();

    const rows = within(dialog).getAllByTestId("version-diff-row");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getAllByText("共同开头")).toHaveLength(2);
    expect(within(rows[1]).getByText("旧中段")).toBeInTheDocument();
    expect(within(rows[1]).getByText("新中段")).toBeInTheDocument();
    expect(within(rows[2]).getAllByText("共同结尾")).toHaveLength(2);
  });

  it("refreshes document versions after approving a confirmation", async () => {
    const user = userEvent.setup();
    let versionCalls = 0;
    let confirmationResolved = false;
    const approvedHistoryItem = {
      id: "confirmation-1",
      action_type: "selection_replace",
      status: "approved",
      payload: { replacement_text: "新文本" },
      document_id: "doc-1",
      before_text: "旧文本",
      after_text: "新文本",
      chapter_title: "第一章",
      resolved_at: "2026-06-14T08:00:00.000Z",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/confirmations/history")) {
        return Promise.resolve(jsonResponse(confirmationResolved ? [approvedHistoryItem] : []));
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
    expect(await screen.findByTestId("confirmation-history-card")).toBeInTheDocument();
    expect(screen.getByText("已写入")).toBeInTheDocument();
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
    await waitForDocumentEditorReady("第一章");
    const titleInput = screen.getByLabelText("章节名称");
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
              tool_calls: [{ id: "tool-1", tool: "create_character_asset", status: "ok" }],
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
    let chapterCreated = false;
    const createdNode = {
      id: "node-created",
      novel_id: "novel-1",
      title: "第一章",
      node_type: "chapter",
      parent_id: null,
      document_id: "doc-created",
      position: 0,
      status: "draft",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(jsonResponse(chapterCreated ? [createdNode] : []));
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
        chapterCreated = true;
        return Promise.resolve(
          sseResponse([
            { type: "delta", content: "第一章已写入工作台。" },
            {
              type: "done",
              message: "第一章已写入工作台。",
              context_status: [],
              conversation_id: "conv-write",
              confirmation: null,
              workspace_nodes: [createdNode],
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
    expect(await screen.findByTestId("workspace-node-title-node-created")).toHaveTextContent("第一章");
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
      if (url.endsWith("/novels/novel-1/confirmations/history")) {
        return Promise.resolve(jsonResponse([]));
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

    expect(await screen.findByTestId("document-inline-confirmation-layer")).toBeInTheDocument();
    expect(await screen.findByTestId("inline-confirmation-confirmation-write")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认写入" }));
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
      if (url.endsWith("/novels/novel-1/confirmations/history")) {
        return Promise.resolve(jsonResponse([]));
      }
      if (url.endsWith("/novels/novel-1/confirmations")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "confirmation-pending",
              action_type: "selection_replace",
              status: "pending",
              payload: { replacement_text: "倒计时：~22天。北郊裂缝E级Boss——约九天后完全显现。" },
              document_id: "doc-1",
              before_text: "倒计时：28天。北郊裂缝E级Boss——约九天后完全显现。",
              after_text: "倒计时：~22天。北郊裂缝E级Boss——约九天后完全显现。",
              chapter_title: "第一章",
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);

    expect(await screen.findByTestId("document-inline-confirmation-layer")).toBeInTheDocument();
    const inlineConfirmation = screen.getByTestId("inline-confirmation-confirmation-pending");
    expect(within(inlineConfirmation).getByText("选区替换")).toBeInTheDocument();
    expect(within(inlineConfirmation).getByText("章节：第一章")).toBeInTheDocument();
    expect(within(inlineConfirmation).getAllByText("修改").length).toBeGreaterThan(0);
    expect(within(inlineConfirmation).getByText("倒计时：28天。北郊裂缝E级Boss——约九天后完全显现。")).toBeInTheDocument();
    expect(within(inlineConfirmation).getByText("倒计时：~22天。北郊裂缝E级Boss——约九天后完全显现。")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-node-pending-write-node-1")).toHaveTextContent("1 处待确认");
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
      if (url.endsWith("/novels/novel-1/confirmations/history")) {
        return Promise.resolve(jsonResponse([]));
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
            { type: "reasoning", content: "整理写入结果并准备回复。" },
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
    expect(await screen.findByText("第一章已写入。")).toBeInTheDocument();
  });

  it("shows thinking indicator after tool call completes", async () => {
    const user = userEvent.setup();
    let releaseReasoning: (() => void) | null = null;
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
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({
                  type: "tool_call",
                  id: "run-thinking",
                  tool: "search_rag",
                  status: "running",
                  args: { query: "主角设定" },
                  summary: null,
                })}\n\n`,
              ),
            );
            window.setTimeout(() => {
              controller.enqueue(
                encoder.encode(
                  `data: ${JSON.stringify({
                    type: "tool_call",
                    id: "run-thinking",
                    tool: "search_rag",
                    status: "ok",
                    args: { query: "主角设定" },
                    summary: "找到 2 条记忆。",
                  })}\n\n`,
                ),
              );
              releaseReasoning = () => {
                controller.enqueue(
                  encoder.encode(
                    `data: ${JSON.stringify({ type: "reasoning", content: "结合检索结果组织回答。" })}\n\n`,
                  ),
                );
                window.setTimeout(() => {
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({ type: "delta", content: "检索完成。" })}\n\n`,
                    ),
                  );
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({
                        type: "done",
                        message: "检索完成。",
                        context_status: [],
                        conversation_id: "conv-thinking",
                        confirmation: null,
                        tool_calls: [
                          {
                            id: "run-thinking",
                            tool: "search_rag",
                            status: "ok",
                            args: { query: "主角设定" },
                            summary: "找到 2 条记忆。",
                          },
                        ],
                      })}\n\n`,
                    ),
                  );
                  controller.close();
                }, 50);
              };
            }, 200);
          },
        });
        return Promise.resolve(
          new Response(stream, {
            headers: { "Content-Type": "text/event-stream" },
            status: 200,
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="workspace" token="test-token" novelId="novel-1" />);
    await user.type(
      screen.getByPlaceholderText("让 Agent 规划、改写、记录记忆或检索上下文"),
      "检索主角设定{Enter}",
    );

    expect(await screen.findByTestId("agent-tool-call-card")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("正在执行：检索上下文")).toBeInTheDocument();
    });
    expect(screen.getByTestId("agent-thinking-indicator")).toHaveAttribute("data-variant", "tool");
    expect(screen.getByTestId("agent-thinking-indicator").closest(".ant-bubble-list")).toBeTruthy();

    await waitFor(() => expect(releaseReasoning).not.toBeNull());
    releaseReasoning!();
    expect(await screen.findByText("思考中")).toBeInTheDocument();
    expect(await screen.findByText(/结合检索结果组织回答/)).toBeInTheDocument();
    expect(await screen.findByText("检索完成。")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId("agent-thinking-indicator")).not.toBeInTheDocument();
    });
  });

  it("scores all chapters with the Agent rubric tool", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "node-1", title: "第一章 钩子", node_type: "chapter", parent_id: null, document_id: "doc-1", position: 0 },
            { id: "node-2", title: "第二章 暗流", node_type: "chapter", parent_id: null, document_id: "doc-2", position: 1 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/agent/tools/score_chapters_with_rubric")) {
        expect(init?.method).toBe("POST");
        return Promise.resolve(
          jsonResponse({
            result: {
              status: "ok",
              scores: [
                {
                  node_id: "node-2",
                  chapter_title: "第二章 暗流",
                  total_score: 6.4,
                  platform_risk: "中",
                  details: {
                    hook: 1.1,
                    progress: 1.2,
                    character: 1,
                    conflict: 1.1,
                    language_originality: 1,
                  },
                  reasons: ["功能章偏重", "AI句式感偏高"],
                  suggestions: ["增加人物选择和章末钩子"],
                },
              ],
              summary: { average_score: 6.4, chapter_count: 1 },
              rubric: { total_points: 10 },
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="scoring" token="test-token" novelId="novel-1" />);

    expect(await screen.findByRole("heading", { name: "章节评分" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始评分" }));

    expect(await screen.findByText("平台风险：中")).toBeInTheDocument();
    expect(screen.getByText("语言原创：1")).toBeInTheDocument();
    expect(screen.getByText(/功能章偏重/)).toBeInTheDocument();
  });

  it("copies a local scoring Agent setup prompt from the scoring page", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<WorkspacePage activeSection="scoring" token="test-token" novelId="novel-1" />);

    expect(await screen.findByRole("heading", { name: "章节评分" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "复制本地评分接入提示" }));

    expect(writeText).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("/local-scoring-skill/SKILL.md");
    expect(copied).toContain("AI_STORY_ACCESS_TOKEN=test-token");
    expect(copied).toContain("ai-story agent manifest");
    expect(copied).toContain("score_chapters_with_rubric");
    expect(await screen.findByText("已复制本地评分接入提示")).toBeInTheDocument();
  });

  it("scores selected chapters from a chapter tree", async () => {
    const user = userEvent.setup();
    let scoreRequestBody: unknown = null;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const conversationResponse = conversationMockResponse(url);
      if (conversationResponse) {
        return Promise.resolve(conversationResponse);
      }
      if (url.endsWith("/novels/novel-1/nodes")) {
        return Promise.resolve(
          jsonResponse([
            { id: "folder-1", title: "第一卷", node_type: "folder", parent_id: null, document_id: null, position: 0 },
            { id: "node-1", title: "第一章 钩子", node_type: "chapter", parent_id: "folder-1", document_id: "doc-1", position: 0 },
            { id: "node-2", title: "第二章 暗流", node_type: "chapter", parent_id: "folder-1", document_id: "doc-2", position: 1 },
            { id: "node-3", title: "第三章 独立章", node_type: "chapter", parent_id: null, document_id: "doc-3", position: 1 },
          ]),
        );
      }
      if (url.endsWith("/novels/novel-1/agent/tools/score_chapters_with_rubric")) {
        scoreRequestBody = init?.body ? JSON.parse(String(init.body)) : null;
        return Promise.resolve(
          jsonResponse({
            result: {
              status: "ok",
              scores: [
                {
                  node_id: "node-1",
                  chapter_title: "第一章 钩子",
                  total_score: 7.2,
                  platform_risk: "低",
                  details: {
                    hook: 1.4,
                    progress: 1.4,
                    character: 1.4,
                    conflict: 1.5,
                    language_originality: 1.5,
                  },
                  reasons: ["章节阅读效果稳定"],
                  suggestions: ["继续保持章末钩子"],
                },
              ],
              summary: { average_score: 7.2, chapter_count: 1 },
              rubric: { total_points: 10 },
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse([]));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<WorkspacePage activeSection="scoring" token="test-token" novelId="novel-1" />);

    expect(await screen.findByRole("heading", { name: "章节评分" })).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByLabelText("评分范围"));
    await user.click(await screen.findByText("指定章节"));
    const scoringTree = await screen.findByLabelText("选择章节");
    expect(scoringTree).toBeInTheDocument();

    const folderTitle = within(scoringTree).getByText("第一卷");
    const folderRow = folderTitle.closest(".ant-tree-treenode") as HTMLElement;
    fireEvent.click(folderRow.querySelector(".ant-tree-checkbox") as HTMLElement);
    expect(await screen.findByText("已选 2 章")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "开始评分" }));

    await waitFor(() => {
      expect(scoreRequestBody).toMatchObject({
        arguments: {
          node_ids: ["node-1", "node-2"],
          scope: "selected",
        },
      });
    });
    expect(await screen.findByText("平台风险：低")).toBeInTheDocument();
  });
});
