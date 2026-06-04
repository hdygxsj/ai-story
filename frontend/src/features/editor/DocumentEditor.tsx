import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Button, Card, Input, Space, Typography } from "antd";
import { useEffect, useRef, useState } from "react";

import type { DocumentBody } from "../../api/documents";

type DocumentEditorProps = {
  chapterTitle?: string | null;
  content?: DocumentBody | null;
  initialText?: string;
  onChange?: (content: DocumentBody) => void;
  onRenameChapter?: (title: string) => void;
  onSelectText?: (text: string) => void;
  onSave?: (content: DocumentBody) => void;
  saveStatus?: "dirty" | "saved" | "saving";
  saving?: boolean;
};

export function DocumentEditor({
  chapterTitle,
  content,
  initialText = "在这里撰写或粘贴章节正文。",
  onChange,
  onRenameChapter,
  onSelectText,
  onSave,
  saveStatus = "saved",
  saving = false,
}: DocumentEditorProps) {
  const applyingExternalContent = useRef(false);
  const [chapterTitleValue, setChapterTitleValue] = useState(chapterTitle ?? "");
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: "开始写这一章...",
      }),
    ],
    content: content ?? `<p>${initialText}</p>`,
    onUpdate: ({ editor: updatedEditor }) => {
      if (applyingExternalContent.current) {
        return;
      }
      onChange?.(updatedEditor.getJSON() as DocumentBody);
    },
    editorProps: {
      attributes: {
        "data-testid": "tiptap-editor",
        style:
          "min-height: calc(100vh - 196px); padding: 30px 44px; border: none; border-radius: 18px; outline: none; background: #fff; box-shadow: inset 0 0 0 1px rgba(15,23,42,0.06); line-height: 1.9; font-size: 16px;",
      },
      handleDOMEvents: {
        keyup: () => {
          handleUseSelection();
          return false;
        },
        mouseup: () => {
          handleUseSelection();
          return false;
        },
      },
    },
  });

  useEffect(() => {
    setChapterTitleValue(chapterTitle ?? "");
  }, [chapterTitle]);

  useEffect(() => {
    if (!editor) {
      return;
    }
    applyingExternalContent.current = true;
    editor.commands.setContent(content ?? `<p>${initialText}</p>`);
    queueMicrotask(() => {
      applyingExternalContent.current = false;
    });
  }, [content, editor, initialText]);

  useEffect(() => {
    document.addEventListener("mouseup", handleUseSelection);
    document.addEventListener("selectionchange", handleUseSelection);

    return () => {
      document.removeEventListener("mouseup", handleUseSelection);
      document.removeEventListener("selectionchange", handleUseSelection);
    };
  });

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        handleSave();
      }
    }

    document.addEventListener("keydown", handleShortcut);
    return () => {
      document.removeEventListener("keydown", handleShortcut);
    };
  });

  function handleUseSelection() {
    const selection = window.getSelection()?.toString().trim();
    const nextSelectedText = selection || "";
    onSelectText?.(nextSelectedText);
  }

  function handleSave() {
    if (!editor) {
      return;
    }
    commitChapterTitle();
    onSave?.(editor.getJSON() as DocumentBody);
  }

  function commitChapterTitle() {
    const nextTitle = chapterTitleValue.trim();
    if (!nextTitle) {
      setChapterTitleValue(chapterTitle ?? "");
      return;
    }
    setChapterTitleValue(nextTitle);
    if (nextTitle !== chapterTitle) {
      onRenameChapter?.(nextTitle);
    }
  }

  return (
    <section style={{ height: "100%", minWidth: 0, padding: 0 }}>
      <Card
        title={
          <div>
            <Input
              aria-label="章节名称"
              onBlur={commitChapterTitle}
              onChange={(event) => setChapterTitleValue(event.target.value)}
              onPressEnter={(event) => event.currentTarget.blur()}
              placeholder="未选择章节"
              style={{
                color: "#111827",
                fontSize: 22,
                fontWeight: 700,
                paddingInline: 0,
              }}
              value={chapterTitleValue}
              variant="borderless"
            />
            <Typography.Text type="secondary">选中文本后会自动进入右侧 Agent 引用区</Typography.Text>
          </div>
        }
        extra={
          <Space>
            <Typography.Text type={saveStatus === "dirty" ? "warning" : "success"}>
              {saveStatus === "dirty" ? "未保存" : saveStatus === "saving" ? "保存中..." : "已保存"}
            </Typography.Text>
            <Button>版本历史</Button>
            <Button loading={saving} onClick={handleSave} title="快捷键：Cmd/Ctrl + S" type="primary">
              保存 Cmd/Ctrl+S
            </Button>
          </Space>
        }
        style={{
          background: "rgba(255,255,255,0.72)",
          border: "none",
          boxShadow: "0 18px 60px rgba(15,23,42,0.08)",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          minHeight: 0,
          minWidth: 0,
        }}
        styles={{ body: { flex: 1, minHeight: 0, overflow: "auto", padding: 14 } }}
      >
        <div
          onKeyUpCapture={handleUseSelection}
          onMouseUpCapture={handleUseSelection}
          style={{ position: "relative" }}
        >
          <EditorContent editor={editor} />
        </div>
      </Card>
    </section>
  );
}
