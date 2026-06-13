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
