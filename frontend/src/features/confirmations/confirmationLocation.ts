import type { Editor } from "@tiptap/react";

import type { Confirmation } from "../../api/confirmations";
import { documentStartPos, findTextRangeInEditor } from "../editor/editorTextPosition";

export function confirmationAnchorText(confirmation: Confirmation): string | null {
  if (confirmation.action_type === "selection_replace" || confirmation.action_type === "rewrite_selection") {
    const selected = confirmation.payload.selected_text;
    return typeof selected === "string" && selected.trim() ? selected.trim() : null;
  }
  if (confirmation.action_type === "document_update") {
    const before = confirmation.before_text?.trim();
    if (before) {
      return before.split("\n\n")[0]?.split("\n")[0] ?? before;
    }
    const after = confirmation.after_text?.trim();
    if (after) {
      return after.split("\n\n")[0]?.split("\n")[0] ?? after;
    }
  }
  return null;
}

export function resolveConfirmationRange(
  editor: Editor,
  confirmation: Confirmation,
): { from: number; to: number } {
  const anchorText = confirmationAnchorText(confirmation);
  if (anchorText) {
    const located = findTextRangeInEditor(editor, anchorText);
    if (located) {
      return located;
    }
  }
  const start = documentStartPos(editor);
  return { from: start, to: Math.min(start + 1, editor.state.doc.content.size) };
}

export function scrollEditorToRange(
  editor: Editor,
  from: number,
  scrollContainer?: HTMLElement | null,
) {
  const container =
    scrollContainer ?? (editor.view.dom.closest(".ant-card-body") as HTMLElement | null) ?? undefined;
  if (!container) {
    return;
  }

  let coords: { top: number };
  try {
    coords = editor.view.coordsAtPos(from);
  } catch {
    return;
  }

  const containerRect = container.getBoundingClientRect();
  const targetTop = coords.top - containerRect.top + container.scrollTop - container.clientHeight / 3;
  const nextTop = Math.max(0, targetTop);
  if (typeof container.scrollTo === "function") {
    container.scrollTo({ top: nextTop, behavior: "smooth" });
  } else {
    container.scrollTop = nextTop;
  }
}

export function focusConfirmationInEditor(
  editor: Editor,
  confirmation: Confirmation,
  scrollContainer?: HTMLElement | null,
) {
  const range = resolveConfirmationRange(editor, confirmation);
  try {
    editor.commands.setTextSelection(range);
  } catch {
    // Headless editors (e.g. jsdom) may not support selection geometry.
  }
  scrollEditorToRange(editor, range.from, scrollContainer);
  return range;
}
