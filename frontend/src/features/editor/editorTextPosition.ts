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

export function documentStartPos(editor: Editor): number {
  const doc = editor.state.doc;
  if (doc.content.size === 0) {
    return 0;
  }
  return 1;
}
