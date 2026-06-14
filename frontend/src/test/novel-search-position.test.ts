import { describe, expect, it } from "vitest";

import type { ProseMirrorNode } from "@tiptap/pm/model";
import { Schema } from "@tiptap/pm/model";

import { mapPlainTextIndexToDocPos } from "../features/editor/editorTextPosition";

const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: {
      content: "text*",
      group: "block",
      parseDOM: [{ tag: "p" }],
      toDOM: () => ["p", 0],
    },
    text: { group: "inline" },
  },
});

function docFromParagraphs(paragraphs: string[]) {
  return schema.node(
    "doc",
    null,
    paragraphs.map((text) => schema.node("paragraph", null, text ? [schema.text(text)] : [])),
  );
}

describe("mapPlainTextIndexToDocPos", () => {
  it("maps paragraph boundaries with double newlines", () => {
    const doc = docFromParagraphs(["灯塔在雾里熄灭。", "灯塔重新点亮。"]) as ProseMirrorNode;
    const secondParagraphStart = mapPlainTextIndexToDocPos(doc, "灯塔在雾里熄灭。\n\n".length);
    expect(secondParagraphStart).not.toBeNull();
    expect(doc.textBetween(secondParagraphStart!, secondParagraphStart! + 2)).toBe("灯塔");
  });
});
