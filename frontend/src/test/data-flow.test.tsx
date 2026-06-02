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
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/novels")) {
          return Promise.resolve(
            jsonResponse([{ id: "novel-1", title: "Fetched Novel", description: "Loaded from API" }]),
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
            ]),
          );
        }
        if (url.endsWith("/documents/doc-1")) {
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

    render(<WorkspacePage token="token" novelId="novel-1" />);

    await user.click(await screen.findByRole("treeitem", { name: /Chapter From API/ }));

    expect(await screen.findByText("Loaded chapter content")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Memory" }));
    expect(await screen.findByText("Core vow")).toBeInTheDocument();
    expect(screen.getByText("OpenAI Default")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Confirmations" }));
    expect(await screen.findByText("rewrite_selection")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Materials" }));
    expect(await screen.findAllByText("Mira")).toHaveLength(2);
    expect(screen.getByText("Storm Night")).toBeInTheDocument();
    expect(screen.getByText("Hiding the map")).toBeInTheDocument();
    expect(screen.getByText("distrusts")).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1", expect.anything()));
  });
});
