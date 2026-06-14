import type { Editor } from "@tiptap/react";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

const TEXT_BLOCK_SEPARATOR = "\n\n";
const TEXT_LEAF_SEPARATOR = "\n";

function plainTextAtDocPos(doc: ProseMirrorNode, pos: number): string {
  return doc.textBetween(0, pos, TEXT_BLOCK_SEPARATOR, TEXT_LEAF_SEPARATOR);
}

export function mapPlainTextIndexToDocPos(doc: ProseMirrorNode, targetIndex: number): number | null {
  const fullLength = plainTextAtDocPos(doc, doc.content.size).length;
  if (targetIndex < 0 || targetIndex > fullLength) {
    return null;
  }

  let low = 0;
  let high = doc.content.size;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (plainTextAtDocPos(doc, mid).length < targetIndex) {
      low = mid + 1;
    } else {
      high = mid;
    }
  }
  return low;
}

export function findTextRangeInEditor(
  editor: Editor,
  searchText: string,
): { from: number; to: number } | null {
  const query = searchText.trim();
  if (!query) {
    return null;
  }

  const doc = editor.state.doc;
  const fullText = plainTextAtDocPos(doc, doc.content.size);
  const startIndex = fullText.indexOf(query);
  if (startIndex === -1) {
    return null;
  }

  const from = mapPlainTextIndexToDocPos(doc, startIndex);
  const to = mapPlainTextIndexToDocPos(doc, startIndex + query.length);
  if (from === null || to === null || to <= from) {
    return null;
  }
  return { from, to };
}

export function focusPlainTextRange(
  editor: Editor,
  startIndex: number,
  length: number,
  scrollContainer?: HTMLElement | null,
) {
  const doc = editor.state.doc;
  const from = mapPlainTextIndexToDocPos(doc, startIndex);
  const to = mapPlainTextIndexToDocPos(doc, startIndex + length);
  if (from === null || to === null || to <= from) {
    return null;
  }

  const range = { from, to };
  try {
    editor.commands.setTextSelection(range);
  } catch {
    // Headless editors (e.g. jsdom) may not support selection geometry.
  }

  const container =
    scrollContainer ?? (editor.view.dom.closest(".ant-card-body") as HTMLElement | null) ?? undefined;
  if (container) {
    let coords: { top: number };
    try {
      coords = editor.view.coordsAtPos(from);
    } catch {
      return range;
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

  return range;
}

export function documentStartPos(editor: Editor): number {
  const doc = editor.state.doc;
  if (doc.content.size === 0) {
    return 0;
  }
  return 1;
}
