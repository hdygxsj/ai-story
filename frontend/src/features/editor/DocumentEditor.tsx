import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Button, Card, Input, Space, Spin, Typography } from "antd";
import { memo, useCallback, useEffect, useRef, useState } from "react";

import type { DocumentBody } from "../../api/documents";
import type { Confirmation } from "../../api/confirmations";
import { throttle } from "../../utils/schedule";
import { focusConfirmationInEditor } from "../confirmations/confirmationLocation";
import { documentBodiesEqual } from "./documentBodyText";
import { documentStartPos, focusPlainTextRange } from "./editorTextPosition";
import { DocumentConfirmationNavigator } from "./DocumentConfirmationNavigator";
import { DocumentEditorConfirmations } from "./DocumentEditorConfirmations";

const EMPTY_DOCUMENT: DocumentBody = { type: "doc", content: [] };

const EDITOR_EXTENSIONS = [
  StarterKit,
  Placeholder.configure({
    placeholder: "开始写这一章...",
  }),
];

type DocumentEditorProps = {
  chapterTitle?: string | null;
  content?: DocumentBody | null;
  documentId?: string | null;
  focusConfirmationId?: string | null;
  focusSearchRange?: { matchIndex: number; matchLength: number } | null;
  loading?: boolean;
  pendingConfirmations?: Confirmation[];
  onApproveConfirmation?: (confirmationId: string) => void;
  onChange?: (content: DocumentBody) => void;
  onFocusConfirmationHandled?: () => void;
  onFocusSearchHandled?: () => void;
  onRejectConfirmation?: (confirmationId: string) => void;
  onRenameChapter?: (title: string) => void;
  onOpenVersionHistory?: () => void;
  onSelectText?: (text: string) => void;
  onSave?: (content: DocumentBody) => void;
  saveStatus?: "dirty" | "saved" | "saving";
  saving?: boolean;
};

export function DocumentEditor(props: DocumentEditorProps) {
  return <DocumentEditorView {...props} />;
}

const DocumentEditorView = memo(function DocumentEditorView({
  chapterTitle,
  content,
  documentId = null,
  focusConfirmationId = null,
  focusSearchRange = null,
  loading = false,
  pendingConfirmations = [],
  onApproveConfirmation,
  onChange,
  onFocusConfirmationHandled,
  onFocusSearchHandled,
  onRejectConfirmation,
  onRenameChapter,
  onOpenVersionHistory,
  onSelectText,
  onSave,
  saveStatus = "saved",
  saving = false,
}: DocumentEditorProps) {
  const applyingExternalContent = useRef(false);
  const editorShellRef = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  const onSaveRef = useRef(onSave);
  const onSelectTextRef = useRef(onSelectText);
  const [activeConfirmationIndex, setActiveConfirmationIndex] = useState(0);
  const [chapterTitleValue, setChapterTitleValue] = useState(chapterTitle ?? "");
  const [pendingSelection, setPendingSelection] = useState("");
  const [selectionToolbarPosition, setSelectionToolbarPosition] = useState<{ left: number; top: number } | null>(null);

  useEffect(() => {
    onChangeRef.current = onChange;
    onSaveRef.current = onSave;
    onSelectTextRef.current = onSelectText;
  }, [onChange, onSave, onSelectText]);

  const handleUseSelection = useCallback(() => {
    const selection = window.getSelection();
    const nextSelectedText = selection?.toString().trim() ?? "";
    if (!nextSelectedText || !selection?.rangeCount || !editorShellRef.current) {
      setPendingSelection("");
      setSelectionToolbarPosition(null);
      return;
    }
    const rangeRect = selection.getRangeAt(0).getBoundingClientRect();
    setPendingSelection(nextSelectedText);
    setSelectionToolbarPosition({
      left: Math.max(12, Math.min(rangeRect.left, window.innerWidth - 120)),
      top: Math.max(12, Math.min(rangeRect.bottom + 8, window.innerHeight - 48)),
    });
  }, []);

  const throttledHandleUseSelection = useRef(throttle(handleUseSelection, 120)).current;

  const editor = useEditor({
    extensions: EDITOR_EXTENSIONS,
    content: content ?? EMPTY_DOCUMENT,
    editable: !loading,
    onUpdate: ({ editor: updatedEditor }) => {
      if (applyingExternalContent.current || loading) {
        return;
      }
      onChangeRef.current?.(updatedEditor.getJSON() as DocumentBody);
    },
    editorProps: {
      attributes: {
        "data-testid": "tiptap-editor",
        style:
          "min-height: 100%; padding: 8px 4px 24px; border: none; outline: none; background: transparent; line-height: 1.9; font-size: 16px;",
      },
      handleDOMEvents: {
        keyup: () => {
          throttledHandleUseSelection();
          return false;
        },
        mouseup: () => {
          throttledHandleUseSelection();
          return false;
        },
      },
    },
  });

  useEffect(() => {
    setChapterTitleValue(chapterTitle ?? "");
  }, [chapterTitle]);

  useEffect(() => {
    const scrollContainer = editorShellRef.current?.closest(".ant-card-body") as HTMLElement | null;
    if (!scrollContainer) {
      return;
    }
    if (typeof scrollContainer.scrollTo === "function") {
      scrollContainer.scrollTo({ left: 0, top: 0, behavior: "auto" });
    } else {
      scrollContainer.scrollTop = 0;
      scrollContainer.scrollLeft = 0;
    }
  }, [documentId]);

  useEffect(() => {
    if (!editor || loading) {
      return;
    }
    const nextContent = content ?? EMPTY_DOCUMENT;
    const currentContent = editor.getJSON() as DocumentBody;
    if (documentBodiesEqual(currentContent, nextContent)) {
      return;
    }
    applyingExternalContent.current = true;
    editor.commands.setContent(nextContent);
    queueMicrotask(() => {
      applyingExternalContent.current = false;
    });
  }, [content, editor, loading]);

  useEffect(() => {
    if (!editor) {
      return;
    }
    editor.setEditable(!loading);
  }, [editor, loading]);

  useEffect(() => {
    if (activeConfirmationIndex >= pendingConfirmations.length) {
      setActiveConfirmationIndex(Math.max(0, pendingConfirmations.length - 1));
    }
  }, [activeConfirmationIndex, pendingConfirmations.length]);

  useEffect(() => {
    if (!editor || loading || !focusConfirmationId) {
      return;
    }
    const confirmation = pendingConfirmations.find((item) => item.id === focusConfirmationId);
    if (!confirmation) {
      return;
    }
    const index = pendingConfirmations.findIndex((item) => item.id === focusConfirmationId);
    if (index >= 0) {
      setActiveConfirmationIndex(index);
    }
    requestAnimationFrame(() => {
      const scrollContainer = editorShellRef.current?.closest(".ant-card-body") as HTMLElement | null;
      focusConfirmationInEditor(editor, confirmation, scrollContainer);
      onFocusConfirmationHandled?.();
    });
  }, [editor, focusConfirmationId, loading, onFocusConfirmationHandled, pendingConfirmations]);

  useEffect(() => {
    if (!editor || loading || !focusSearchRange) {
      return;
    }
    requestAnimationFrame(() => {
      const scrollContainer = editorShellRef.current?.closest(".ant-card-body") as HTMLElement | null;
      if (focusSearchRange.matchLength > 0) {
        focusPlainTextRange(editor, focusSearchRange.matchIndex, focusSearchRange.matchLength, scrollContainer);
      } else {
        const start = documentStartPos(editor);
        focusPlainTextRange(editor, start, 1, scrollContainer);
      }
      onFocusSearchHandled?.();
    });
  }, [editor, focusSearchRange, loading, onFocusSearchHandled]);

  function handleNavigateConfirmation(index: number) {
    setActiveConfirmationIndex(index);
    const confirmation = pendingConfirmations[index];
    if (!editor || !confirmation) {
      return;
    }
    const scrollContainer = editorShellRef.current?.closest(".ant-card-body") as HTMLElement | null;
    focusConfirmationInEditor(editor, confirmation, scrollContainer);
  }

  const highlightedConfirmationId =
    focusConfirmationId ?? pendingConfirmations[activeConfirmationIndex]?.id ?? null;

  useEffect(() => {
    const shell = editorShellRef.current;
    if (!shell) {
      return;
    }

    shell.addEventListener("mouseup", throttledHandleUseSelection);
    document.addEventListener("selectionchange", throttledHandleUseSelection);

    return () => {
      shell.removeEventListener("mouseup", throttledHandleUseSelection);
      document.removeEventListener("selectionchange", throttledHandleUseSelection);
    };
  }, [throttledHandleUseSelection]);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!editor) {
          return;
        }
        handleSaveRef.current();
      }
    }

    document.addEventListener("keydown", handleShortcut);
    return () => {
      document.removeEventListener("keydown", handleShortcut);
    };
  }, [editor]);

  function handleQuoteSelection() {
    if (!pendingSelection) {
      return;
    }
    onSelectTextRef.current?.(pendingSelection);
    setPendingSelection("");
    setSelectionToolbarPosition(null);
  }

  function handleSave() {
    if (!editor) {
      return;
    }
    commitChapterTitle();
    onSaveRef.current?.(editor.getJSON() as DocumentBody);
  }

  const handleSaveRef = useRef(handleSave);
  handleSaveRef.current = handleSave;

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
              disabled={loading}
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
            <Typography.Text type="secondary">选中文字后可从浮动工具条引用到 Agent</Typography.Text>
          </div>
        }
        extra={
          <Space>
            <Typography.Text type={saveStatus === "dirty" ? "warning" : "success"}>
              {saveStatus === "dirty" ? "未保存" : saveStatus === "saving" ? "保存中..." : "已保存"}
            </Typography.Text>
            <Button disabled={loading} onClick={onOpenVersionHistory}>
              版本历史
            </Button>
            <Button disabled={loading} loading={saving} onClick={handleSave} title="快捷键：Cmd/Ctrl + S" type="primary">
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
        styles={{ body: { flex: 1, minHeight: 0, overflow: "auto", padding: "0 18px 18px" } }}
      >
        {!loading && pendingConfirmations.length > 1 ? (
          <DocumentConfirmationNavigator
            activeIndex={activeConfirmationIndex}
            onSelect={handleNavigateConfirmation}
            total={pendingConfirmations.length}
          />
        ) : null}
        <div
          ref={editorShellRef}
          style={{ height: "100%", minHeight: 240, position: "relative" }}
        >
          <EditorContent editor={editor} />
          {!loading && editor && pendingConfirmations.length > 0 && onApproveConfirmation && onRejectConfirmation ? (
            <DocumentEditorConfirmations
              confirmations={pendingConfirmations}
              disabled={loading}
              editor={editor}
              highlightedConfirmationId={highlightedConfirmationId}
              onApprove={onApproveConfirmation}
              onReject={onRejectConfirmation}
              shellRef={editorShellRef}
            />
          ) : null}
          {loading ? (
            <div
              aria-busy="true"
              aria-label="正文加载中"
              data-testid="document-editor-loading"
              style={{
                alignItems: "center",
                background: "rgba(255,255,255,0.72)",
                display: "flex",
                inset: 0,
                justifyContent: "center",
                position: "absolute",
                zIndex: 5,
              }}
            >
              <Spin size="large" />
            </div>
          ) : null}
          {!loading && pendingSelection && selectionToolbarPosition ? (
            <Space
              aria-label="选中文本操作"
              size={4}
              style={{
                background: "#ffffff",
                border: "1px solid rgba(15,23,42,0.10)",
                borderRadius: 10,
                boxShadow: "0 10px 30px rgba(15,23,42,0.14)",
                left: selectionToolbarPosition.left,
                padding: 4,
                position: "fixed",
                top: selectionToolbarPosition.top,
                zIndex: 10,
              }}
            >
              <Button onMouseDown={(event) => event.preventDefault()} onClick={handleQuoteSelection} size="small" type="text">
                引用
              </Button>
            </Space>
          ) : null}
        </div>
      </Card>
    </section>
  );
});
