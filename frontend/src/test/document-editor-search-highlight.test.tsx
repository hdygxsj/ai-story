import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentEditor } from "../features/editor/DocumentEditor";

describe("DocumentEditor search highlighting", () => {
  it("highlights the located search range in the editor body", async () => {
    const onFocusSearchHandled = vi.fn();

    render(
      <DocumentEditor
        chapterTitle="第三十一章"
        content={{
          type: "doc",
          content: [
            {
              type: "paragraph",
              content: [{ type: "text", text: "左手握着断刀——唐刀碎片，二十五厘米。" }],
            },
          ],
        }}
        documentId="doc-1"
        focusSearchRange={{ matchIndex: "左手握着断刀——".length, matchLength: "唐刀".length }}
        onFocusSearchHandled={onFocusSearchHandled}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("document-editor-loading")).not.toBeInTheDocument();
      const highlight = document.querySelector(".document-search-highlight");
      expect(highlight).not.toBeNull();
      expect(highlight).toHaveTextContent("唐刀");
    });
    expect(onFocusSearchHandled).toHaveBeenCalledTimes(1);
  });
});
