import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ContextStatusBar } from "../features/agent/ContextStatusBar";

describe("ContextStatusBar", () => {
  it("groups repeated context sources into one counted chip", () => {
    render(
      <ContextStatusBar
        detail={{
          usage_ratio: 0.02,
          warnings: [],
          items: [
            { source: "user_instruction", tokens: 4, compressed: false },
            { source: "structured_memory", tokens: 20, compressed: false },
            { source: "structured_memory", tokens: 30, compressed: false },
            { source: "rag_result", tokens: 10, compressed: false },
            { source: "rag_result", tokens: 12, compressed: true },
          ],
        }}
      />,
    );

    expect(screen.getByText("素材 2")).toBeInTheDocument();
    expect(screen.getByText("RAG 2（已压缩）")).toBeInTheDocument();
    expect(screen.getAllByText(/素材/)).toHaveLength(1);
    expect(screen.getAllByText(/RAG/)).toHaveLength(1);
  });
});
