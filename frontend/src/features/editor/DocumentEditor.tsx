import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Button, Card, Space, Typography } from "antd";
import { useEffect } from "react";

import type { DocumentBody } from "../../api/documents";

type DocumentEditorProps = {
  content?: DocumentBody | null;
  initialText?: string;
  onSelectText?: (text: string) => void;
  onSave?: (content: DocumentBody) => void;
  saving?: boolean;
};

export function DocumentEditor({
  content,
  initialText = "Write or paste chapter text here.",
  onSelectText,
  onSave,
  saving = false,
}: DocumentEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: "Start writing the chapter...",
      }),
    ],
    content: content ?? `<p>${initialText}</p>`,
    editorProps: {
      attributes: {
        "data-testid": "tiptap-editor",
        style:
          "min-height: 420px; padding: 16px; border: 1px solid #d9d9d9; border-radius: 8px; outline: none;",
      },
    },
  });

  useEffect(() => {
    if (!editor) {
      return;
    }
    editor.commands.setContent(content ?? `<p>${initialText}</p>`);
  }, [content, editor, initialText]);

  function handleUseSelection() {
    const selection = window.getSelection()?.toString().trim();
    onSelectText?.(selection || editor?.getText() || "");
  }

  function handleSave() {
    if (!editor) {
      return;
    }
    onSave?.(editor.getJSON() as DocumentBody);
  }

  return (
    <section style={{ height: "100%", padding: 16 }}>
      <Card
        title={<Typography.Title level={2}>Chapter Editor</Typography.Title>}
        extra={
          <Space>
            <Button>Version History</Button>
            <Button loading={saving} onClick={handleSave}>
              Save
            </Button>
            <Button onClick={handleUseSelection} type="primary">
              Ask AI to rewrite selection
            </Button>
          </Space>
        }
        style={{ height: "100%" }}
      >
        <EditorContent editor={editor} />
      </Card>
    </section>
  );
}
