import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NovelList } from "../features/novels/NovelList";
import { WorkspacePage } from "../features/workspace/WorkspacePage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

describe("frontend data flow", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/novels")) {
          return Promise.resolve(
            jsonResponse([{ id: "novel-1", title: "Fetched Novel", description: "Loaded from API" }]),
          );
        }
        if (url.endsWith("/novels/novel-1/nodes") && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse({
              id: "node-2",
              novel_id: "novel-1",
              parent_id: null,
              document_id: "doc-2",
              title: "新章节",
              node_type: "chapter",
              status: "draft",
              position: 1,
            }),
          );
        }
        if (url.endsWith("/novels/novel-1/nodes/reorder") && init?.method === "PATCH") {
          const body = JSON.parse(String(init.body));
          const status = body.items?.[0]?.status ?? "draft";
          return Promise.resolve(
            jsonResponse([
              {
                id: "node-1",
                novel_id: "novel-1",
                parent_id: null,
                document_id: "doc-1",
                title: "Chapter From API",
                node_type: "chapter",
                status,
                position: 0,
              },
              {
                id: "node-3",
                novel_id: "novel-1",
                parent_id: null,
                document_id: "doc-3",
                title: "Second Chapter",
                node_type: "chapter",
                status: "draft",
                position: 1,
              },
            ]),
          );
        }
        if (url.endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH") {
          return Promise.resolve(
            jsonResponse({
              id: "node-1",
              novel_id: "novel-1",
              parent_id: null,
              document_id: "doc-1",
              title: "重命名章节",
              node_type: "chapter",
              status: "draft",
              position: 0,
            }),
          );
        }
        if (url.endsWith("/novels/novel-1/nodes")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "node-1",
                novel_id: "novel-1",
                parent_id: null,
                document_id: "doc-1",
                title: "Chapter From API",
                node_type: "chapter",
                status: "draft",
                position: 0,
              },
              {
                id: "node-3",
                novel_id: "novel-1",
                parent_id: null,
                document_id: "doc-3",
                title: "Second Chapter",
                node_type: "chapter",
                status: "draft",
                position: 1,
              },
            ]),
          );
        }
        if (url.endsWith("/documents/doc-1")) {
          if (init?.method === "PATCH") {
            return Promise.resolve(
              jsonResponse({
                id: "doc-1",
                novel_id: "novel-1",
                content: JSON.parse(String(init.body)).content,
              }),
            );
          }
          return Promise.resolve(
            jsonResponse({
              id: "doc-1",
              novel_id: "novel-1",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "Loaded chapter content" }] }],
              },
            }),
          );
        }
        if (url.endsWith("/documents/doc-1/versions")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/documents/doc-3")) {
          return Promise.resolve(
            jsonResponse({
              id: "doc-3",
              novel_id: "novel-1",
              content: {
                type: "doc",
                content: [{ type: "paragraph", content: [{ type: "text", text: "Second chapter content" }] }],
              },
            }),
          );
        }
        if (url.endsWith("/documents/doc-3/versions")) {
          return Promise.resolve(jsonResponse([]));
        }
        if (url.endsWith("/novels/novel-1/memory-review-items")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "memory-review-1",
                memory_type: "key_memory",
                title: "Core vow",
                body: "Never forget the lighthouse.",
                importance: 90,
                status: "pending",
              },
            ]),
          );
        }
        if (url.endsWith("/novels/novel-1/confirmations")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "confirmation-1",
                action_type: "rewrite_selection",
                status: "pending",
                payload: { replacement_text: "A sharper rewrite." },
              },
            ]),
          );
        }
        if (url.endsWith("/model-profiles")) {
          return Promise.resolve(
            jsonResponse([
              {
                id: "profile-1",
                name: "OpenAI Default",
                provider_kind: "openai",
                chat_model: "gpt-4o",
                writing_model: "gpt-4o",
                summary_model: "gpt-4o-mini",
                embedding_model: "text-embedding-3-small",
              },
            ]),
          );
        }
        if (url.endsWith("/novels/novel-1/creative-assets")) {
          return Promise.resolve(
            jsonResponse([{ id: "asset-1", asset_type: "character", name: "Mira", summary: "Lighthouse keeper" }]),
          );
        }
        if (url.endsWith("/novels/novel-1/timeline-events")) {
          return Promise.resolve(jsonResponse([{ id: "event-1", title: "Storm Night", event_time: "Chapter 3" }]));
        }
        if (url.endsWith("/novels/novel-1/character-states")) {
          return Promise.resolve(jsonResponse([{ id: "state-1", character_name: "Mira", state: "Hiding the map" }]));
        }
        if (url.endsWith("/novels/novel-1/relationship-edges")) {
          return Promise.resolve(
            jsonResponse([{ id: "edge-1", source_character: "Mira", target_character: "Jon", relationship_type: "distrusts" }]),
          );
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads novels when the novel list mounts", async () => {
    render(<NovelList token="token" onSelectNovel={() => undefined} />);

    expect(await screen.findByText("Fetched Novel")).toBeInTheDocument();
  });

  it("loads workspace nodes and selected document content from APIs", async () => {
    const user = userEvent.setup();

    const { rerender } = render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Agent" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共创 Agent" })).toBeInTheDocument();
    await user.click(await screen.findByText("Chapter From API"));

    expect(await screen.findByText("Loaded chapter content")).toBeInTheDocument();
    rerender(<WorkspacePage activeSection="memory" token="token" novelId="novel-1" />);
    expect(await screen.findByText("Core vow")).toBeInTheDocument();
    expect(screen.getByText("OpenAI Default")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共创 Agent" })).toBeInTheDocument();
    rerender(<WorkspacePage activeSection="confirmations" token="token" novelId="novel-1" />);
    expect(await screen.findByText("rewrite_selection")).toBeInTheDocument();
    rerender(<WorkspacePage activeSection="materials" token="token" novelId="novel-1" />);
    expect(await screen.findAllByText("Mira")).toHaveLength(2);
    expect(screen.getByText("Storm Night")).toBeInTheDocument();
    expect(screen.getByText("Hiding the map")).toBeInTheDocument();
    expect(screen.getByText("distrusts")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "共创 Agent" })).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1", expect.anything()));
  });

  it("creates a new chapter from the workspace button", async () => {
    const user = userEvent.setup();

    render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);
    await user.click(screen.getByRole("button", { name: /新建章节/ }));

    expect(await screen.findByText("新章节")).toBeInTheDocument();
    await waitFor(() => {
      const createCall = vi.mocked(fetch).mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes") && init?.method === "POST",
      );
      expect(createCall).toBeTruthy();
      expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({
        node_type: "chapter",
        parent_id: null,
        title: "新章节",
      });
    });
  });

  it("creates a sibling chapter from a chapter context menu", async () => {
    const user = userEvent.setup();

    render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);
    await user.pointer({ keys: "[MouseRight]", target: await screen.findByText("Chapter From API") });
    await user.click(await screen.findByRole("menuitem", { name: "新建章节" }));

    await waitFor(() => {
      const createCall = vi.mocked(fetch).mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes") && init?.method === "POST",
      );
      expect(createCall).toBeTruthy();
      expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({
        node_type: "chapter",
        parent_id: null,
        title: "新章节",
      });
    });
  });

  it("renames a workspace node from the chapter tree", async () => {
    const user = userEvent.setup();

    render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);
    await user.click(await screen.findByRole("button", { name: "重命名 Chapter From API" }));
    const renameInputs = await screen.findAllByLabelText("章节名称");
    const modalInput = renameInputs.at(-1);
    expect(modalInput).toBeTruthy();
    await user.clear(modalInput as HTMLElement);
    await user.type(modalInput as HTMLElement, "重命名章节");
    await user.click(screen.getByRole("button", { name: /确\s*定/ }));

    await waitFor(() => expect(screen.getAllByText("重命名章节").length).toBeGreaterThanOrEqual(1));
    await waitFor(() => {
      const renameCall = vi.mocked(fetch).mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes/node-1") && init?.method === "PATCH",
      );
      expect(renameCall).toBeTruthy();
      expect(JSON.parse(String(renameCall?.[1]?.body))).toMatchObject({ title: "重命名章节" });
    });
  });

  it("moves workspace nodes to the recycle bin and restores them", async () => {
    const user = userEvent.setup();

    render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);
    await user.click(await screen.findByRole("button", { name: "删除 Chapter From API" }));

    await waitFor(() => {
      const trashCall = vi.mocked(fetch).mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes/reorder") && String(init?.body).includes("\"status\":\"trashed\""),
      );
      expect(trashCall).toBeTruthy();
    });
    expect(await screen.findByLabelText("回收站")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "恢复 Chapter From API" }));
    await waitFor(() => {
      const restoreCall = vi.mocked(fetch).mock.calls.find(
        ([url, init]) => String(url).endsWith("/novels/novel-1/nodes/reorder") && String(init?.body).includes("\"status\":\"draft\""),
      );
      expect(restoreCall).toBeTruthy();
    });
  });

  it("switches chapters without leaking the previous document and shows save feedback", async () => {
    const user = userEvent.setup();

    render(<WorkspacePage activeSection="workspace" token="token" novelId="novel-1" />);
    await user.click(await screen.findByText("Second Chapter"));
    expect(await screen.findByText("Second chapter content")).toBeInTheDocument();
    await user.click(await screen.findByText("Chapter From API"));

    expect(await screen.findByText("Loaded chapter content")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /保\s*存/ }));
    expect(await screen.findByText("已保存")).toBeInTheDocument();
  });
});
