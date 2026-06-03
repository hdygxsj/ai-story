import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "../features/workspace/WorkspacePage";

describe("WorkspacePage", () => {
  it("renders a top-tab novel IDE without sidebars", () => {
    render(<WorkspacePage token="test-token" novelId="novel-1" />);

    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Editor" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Memory" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Confirmations" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Materials" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chapter Editor" })).toBeInTheDocument();
    expect(screen.getByTestId("tiptap-editor")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Document editor" })).not.toBeInTheDocument();
  });
});
