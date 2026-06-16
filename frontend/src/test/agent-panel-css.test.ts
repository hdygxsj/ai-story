import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("agent panel message styling", () => {
  it("keeps normal user and assistant bubbles as visible cards", () => {
    const css = readFileSync(resolve(__dirname, "../features/agent/agent-panel.css"), "utf8");

    expect(css).not.toMatch(
      /\.agent-panel-messages\s+\.ant-bubble:not\(:has\(\.agent-tool-call-card\)\)\s+\.ant-bubble-content\s*\{[^}]*background:\s*transparent[^}]*padding:\s*0[^}]*\}/s,
    );
    expect(css).toContain(".agent-panel-messages .ant-bubble:not(:has(.agent-tool-call-card)) .ant-bubble-content");
    expect(css).toContain("box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08)");
  });
});
