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

export function confirmationStatusLabel(status: string): string {
  switch (status) {
    case "approved":
      return "已写入";
    case "rejected":
      return "已拒绝";
    case "pending":
      return "待确认";
    default:
      return status;
  }
}

export function formatConfirmationTime(value?: string | null): string {
  if (!value) {
    return "时间未知";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间未知";
  }
  return date.toLocaleString();
}

export function confirmationHistoryPreview(confirmation: Confirmation): string {
  if (confirmation.status === "approved") {
    const after = confirmation.after_text?.trim();
    if (after) {
      return after.length > 120 ? `${after.slice(0, 120)}…` : after;
    }
  }
  if (confirmation.status === "rejected") {
    const before = confirmation.before_text?.trim();
    if (before) {
      return `未写入，原内容：${before.length > 80 ? `${before.slice(0, 80)}…` : before}`;
    }
    return "已拒绝本次写入";
  }
  return confirmationPreview(confirmation.payload);
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

export function pendingDocumentWriteCountsByDocumentId(items: Confirmation[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of pendingDocumentWriteConfirmations(items)) {
    if (!item.document_id) {
      continue;
    }
    counts[item.document_id] = (counts[item.document_id] ?? 0) + 1;
  }
  return counts;
}
