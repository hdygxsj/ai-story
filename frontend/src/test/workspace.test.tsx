import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

describe("WorkspacePage", () => {
  it("renders the production three-pane novel IDE shell", () => {
    render(<WorkspacePage token="test-token" novelId="novel-1" />);

    expect(screen.getByRole("heading", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chapter Editor" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Memory" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Confirmations" })).toBeInTheDocument();
    expect(screen.getByTestId("tiptap-editor")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Document editor" })).not.toBeInTheDocument();
  });
});
