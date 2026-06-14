import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentThinkingIndicator } from "../features/agent/AgentThinkingIndicator";

describe("AgentThinkingIndicator", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-14T10:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows animated thinking label with elapsed seconds", () => {
    render(<AgentThinkingIndicator startedAt={Date.now() - 2500} />);

    expect(screen.getByTestId("agent-thinking-indicator")).toBeInTheDocument();
    expect(screen.getByText("思考中")).toBeInTheDocument();
    expect(screen.getByText("2s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("3s")).toBeInTheDocument();
  });

  it("shows custom activity label", () => {
    render(<AgentThinkingIndicator label="正在执行：检索上下文" startedAt={Date.now()} variant="tool" />);

    expect(screen.getByText("正在执行：检索上下文")).toBeInTheDocument();
    expect(screen.getByTestId("agent-thinking-indicator")).toHaveAttribute("data-variant", "tool");
  });

  it("shows compact reasoning preview when provided", () => {
    render(
      <AgentThinkingIndicator
        content={"先检查章节结构\n再决定写入位置"}
        startedAt={Date.now()}
      />,
    );

    expect(screen.getByText(/先检查章节结构/)).toBeInTheDocument();
  });
});
