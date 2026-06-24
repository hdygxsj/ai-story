import { Extension } from "@tiptap/core";
import type { Editor } from "@tiptap/react";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

type SearchHighlightRange = { from: number; to: number } | null;

const searchHighlightPluginKey = new PluginKey<SearchHighlightRange>("documentSearchHighlight");

export const SearchHighlightExtension = Extension.create({
  name: "documentSearchHighlight",

  addProseMirrorPlugins() {
    return [
      new Plugin<SearchHighlightRange>({
        key: searchHighlightPluginKey,
        props: {
          decorations(state) {
            const range = searchHighlightPluginKey.getState(state);
            if (!range || range.to <= range.from) {
              return null;
            }
            return DecorationSet.create(state.doc, [
              Decoration.inline(range.from, range.to, {
                class: "document-search-highlight",
                "data-testid": "document-search-highlight",
              }),
            ]);
          },
        },
        state: {
          apply(transaction, currentRange) {
            const meta = transaction.getMeta(searchHighlightPluginKey) as SearchHighlightRange | undefined;
            if (meta !== undefined) {
              return meta;
            }
            if (!transaction.docChanged || !currentRange) {
              return currentRange;
            }
            const from = transaction.mapping.map(currentRange.from);
            const to = transaction.mapping.map(currentRange.to);
            if (to <= from || from < 0 || to > transaction.doc.content.size) {
              return null;
            }
            return { from, to };
          },
          init() {
            return null;
          },
        },
      }),
    ];
  },
});

export function setSearchHighlight(editor: Editor, range: SearchHighlightRange) {
  editor.view.dispatch(editor.state.tr.setMeta(searchHighlightPluginKey, range));
}
