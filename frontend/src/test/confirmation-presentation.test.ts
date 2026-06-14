import { describe, expect, it } from "vitest";

import {
  isDocumentWriteConfirmation,
  pendingDocumentWriteConfirmationIds,
  pendingDocumentWriteConfirmations,
  pendingDocumentWriteCountsByDocumentId,
} from "../features/confirmations/confirmationPresentation";
import type { Confirmation } from "../api/confirmations";

describe("confirmationPresentation document write helpers", () => {
  const items: Confirmation[] = [
    {
      id: "write-1",
      action_type: "document_update",
      status: "pending",
      payload: {},
      document_id: "doc-1",
    },
    {
      id: "other-1",
      action_type: "organize_workspace",
      status: "pending",
      payload: {},
    },
    {
      id: "write-2",
      action_type: "rewrite_selection",
      status: "approved",
      payload: {},
      document_id: "doc-2",
    },
  ];

  it("identifies document write confirmations", () => {
    expect(isDocumentWriteConfirmation(items[0])).toBe(true);
    expect(isDocumentWriteConfirmation(items[1])).toBe(false);
  });

  it("filters pending document write confirmations and document ids", () => {
    expect(pendingDocumentWriteConfirmations(items)).toEqual([items[0]]);
    expect(pendingDocumentWriteConfirmationIds(items)).toEqual(["doc-1"]);
    expect(pendingDocumentWriteCountsByDocumentId(items)).toEqual({ "doc-1": 1 });
  });
});
