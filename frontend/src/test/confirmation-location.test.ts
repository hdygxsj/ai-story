import { describe, expect, it } from "vitest";

import type { Confirmation } from "../api/confirmations";
import { confirmationAnchorText } from "../features/confirmations/confirmationLocation";

describe("confirmationAnchorText", () => {
  it("uses selected text for selection replace actions", () => {
    const confirmation = {
      id: "c-1",
      action_type: "selection_replace",
      status: "pending",
      payload: { selected_text: "  选中片段  " },
    } as Confirmation;

    expect(confirmationAnchorText(confirmation)).toBe("选中片段");
  });

  it("prefers before_text for document updates", () => {
    const confirmation = {
      id: "c-2",
      action_type: "document_update",
      status: "pending",
      payload: {},
      before_text: "旧正文第一段\n第二段",
      after_text: "新正文",
    } as Confirmation;

    expect(confirmationAnchorText(confirmation)).toBe("旧正文第一段");
  });

  it("falls back to after_text when before_text is missing", () => {
    const confirmation = {
      id: "c-3",
      action_type: "document_update",
      status: "pending",
      payload: {},
      after_text: "新增段落\n后续内容",
    } as Confirmation;

    expect(confirmationAnchorText(confirmation)).toBe("新增段落");
  });
});
