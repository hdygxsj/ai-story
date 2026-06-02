import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

describe("WorkspacePage", () => {
  it("renders the three-pane novel IDE", () => {
    render(<WorkspacePage token="test-token" novelId="novel-1" />);

    expect(screen.getByText("Workspace")).toBeTruthy();
    expect(screen.getByText("Editor")).toBeTruthy();
    expect(screen.getByText("Agent")).toBeTruthy();
  });
});
