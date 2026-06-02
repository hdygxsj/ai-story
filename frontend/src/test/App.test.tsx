import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("App", () => {
  it("renders the product name and tagline", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI Story" })).toBeInTheDocument();
    expect(screen.getByText("Agent-first novel creation IDE")).toBeInTheDocument();
  });

  it("opens demo workspace", () => {
    render(<App />);

    fireEvent.click(screen.getByText("Continue in demo mode"));
    fireEvent.click(screen.getByText("Open demo novel"));

    expect(screen.getByText("Workspace")).toBeTruthy();
    expect(screen.getByText("Editor")).toBeTruthy();
    expect(screen.getByText("Agent")).toBeTruthy();
  });
});
