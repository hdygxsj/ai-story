import type { DocumentBody } from "../../api/documents";

export function extractDocumentBodyText(content: DocumentBody | null | undefined): string {
  const parts: string[] = [];

  function visit(node: unknown) {
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    if (!node || typeof node !== "object") {
      return;
    }
    const current = node as { content?: unknown; text?: unknown };
    if (typeof current.text === "string") {
      parts.push(current.text);
    }
    if (current.content) {
      visit(current.content);
    }
  }

  visit(content);
  return parts.join("");
}

export function documentBodiesEqual(
  left: DocumentBody | null | undefined,
  right: DocumentBody | null | undefined,
): boolean {
  if (left === right) {
    return true;
  }
  if (!left || !right) {
    return false;
  }
  return extractDocumentBodyText(left) === extractDocumentBodyText(right);
}
