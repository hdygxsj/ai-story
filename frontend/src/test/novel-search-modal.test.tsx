import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NovelSearchModal } from "../features/workspace/NovelSearchModal";

vi.mock("../api/search", () => ({
  searchNovelDocuments: vi.fn(async () => [
    {
      document_id: "doc-1",
      node_id: "node-1",
      node_title: "第一章",
      match_index: 0,
      match_length: 2,
      matched_text: "灯塔",
      snippet: "灯塔在雾里熄灭。",
      match_source: "body",
      total_matches_in_document: 1,
      occurrence_index: 0,
    },
  ]),
}));

describe("NovelSearchModal", () => {
  it("searches and lets the user open a hit", async () => {
    const onSelectHit = vi.fn();
    render(
      <NovelSearchModal
        novelId="novel-1"
        onClose={() => undefined}
        onSelectHit={onSelectHit}
        open
        token="token-1"
      />,
    );

    fireEvent.change(screen.getByTestId("novel-search-input"), { target: { value: "灯塔" } });

    await waitFor(() => {
      expect(screen.getByText("第一章")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("novel-search-open-doc-1-0"));
    expect(onSelectHit).toHaveBeenCalledWith(
      expect.objectContaining({
        document_id: "doc-1",
        node_title: "第一章",
      }),
    );
  });
});
