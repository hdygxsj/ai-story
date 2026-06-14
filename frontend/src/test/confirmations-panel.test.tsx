import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Confirmation } from "../api/confirmations";
import { ConfirmationsPanel } from "../features/confirmations/ConfirmationsPanel";

describe("ConfirmationsPanel", () => {
  const pending: Confirmation = {
    id: "pending-1",
    action_type: "document_update",
    status: "pending",
    payload: { content: "新正文" },
    document_id: "doc-1",
    before_text: "旧正文",
    after_text: "新正文",
    chapter_title: "第一章",
  };

  const history: Confirmation = {
    id: "history-1",
    action_type: "selection_replace",
    status: "approved",
    payload: {},
    document_id: "doc-1",
    before_text: "旧句子",
    after_text: "新句子",
    chapter_title: "第二章",
    resolved_at: "2026-06-14T08:00:00.000Z",
  };

  it("shows pending items and confirmation history separately", () => {
    render(
      <ConfirmationsPanel
        confirmationCount={1}
        confirmationHistory={[history]}
        confirmations={[pending]}
        onApprove={() => undefined}
        onLocate={() => undefined}
        onReject={() => undefined}
      />,
    );

    expect(screen.getByTestId("confirmations-pending-section")).toBeInTheDocument();
    expect(screen.getByTestId("confirmations-history-section")).toBeInTheDocument();
    expect(screen.getByTestId("agent-write-confirmation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "定位正文" })).toBeInTheDocument();
    expect(screen.getByTestId("confirmation-history-card")).toBeInTheDocument();
    expect(screen.getByText("已写入")).toBeInTheDocument();
    expect(screen.getByText("章节：第二章")).toBeInTheDocument();
    expect(screen.queryByText(/已保存版本/)).not.toBeInTheDocument();
  });
});
