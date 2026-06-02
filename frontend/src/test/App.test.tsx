import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../App";

describe("App", () => {
  it("renders the product name and tagline", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI Story" })).toBeInTheDocument();
    expect(screen.getByText("Agent-first novel creation IDE")).toBeInTheDocument();
  });

  it("starts from a real account workflow without demo shortcuts", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Continue in demo mode")).not.toBeInTheDocument();
  });
});
