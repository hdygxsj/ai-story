import type { Confirmation } from "../../api/confirmations";

export function confirmationPreview(payload: Record<string, unknown>): string {
  if (typeof payload.content === "string") {
    return payload.content;
  }
  if (typeof payload.replacement_text === "string") {
    return payload.replacement_text;
  }
  return "";
}

export function confirmationActionLabel(actionType: string): string {
  switch (actionType) {
    case "document_update":
      return "整章更新";
    case "selection_replace":
      return "选区替换";
    case "rewrite_selection":
      return "段落改写";
    case "version_restore":
      return "版本恢复";
    default:
      return actionType;
  }
}

export function pendingConfirmations(items: Confirmation[]): Confirmation[] {
  return items.filter((item) => item.status === "pending");
}

const DOCUMENT_WRITE_ACTION_TYPES = new Set([
  "document_update",
  "selection_replace",
  "rewrite_selection",
  "version_restore",
]);

export function isDocumentWriteConfirmation(confirmation: Confirmation): boolean {
  return DOCUMENT_WRITE_ACTION_TYPES.has(confirmation.action_type);
}

export function pendingDocumentWriteConfirmations(items: Confirmation[]): Confirmation[] {
  return pendingConfirmations(items).filter(isDocumentWriteConfirmation);
}

export function pendingDocumentWriteConfirmationIds(items: Confirmation[]): string[] {
  return pendingDocumentWriteConfirmations(items)
    .map((item) => item.document_id)
    .filter((documentId): documentId is string => Boolean(documentId));
}
