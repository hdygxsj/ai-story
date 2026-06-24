import { Button, Space, Tag, Typography } from "antd";
import type { Editor } from "@tiptap/react";
import type { RefObject } from "react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { Confirmation } from "../../api/confirmations";
import { createAnimationFrameScheduler } from "../../utils/schedule";
import { ConfirmationDiffView } from "../confirmations/ConfirmationDiffView";
import { confirmationAnchorText } from "../confirmations/confirmationLocation";
import { confirmationActionLabel } from "../confirmations/confirmationPresentation";
import { documentStartPos, findTextRangeInEditor } from "./editorTextPosition";

import "./document-editor-confirmations.css";

type DocumentEditorConfirmationsProps = {
  confirmations: Confirmation[];
  disabled?: boolean;
  editor: Editor;
  highlightedConfirmationId?: string | null;
  onApprove: (confirmationId: string) => void;
  onReject: (confirmationId: string) => void;
  shellRef: RefObject<HTMLDivElement | null>;
};

type PositionedConfirmation = {
  confirmation: Confirmation;
  top: number;
};

function resolveAnchorPos(editor: Editor, confirmation: Confirmation): number {
  const anchorText = confirmationAnchorText(confirmation);
  if (anchorText) {
    const located = findTextRangeInEditor(editor, anchorText);
    if (located) {
      return located.from;
    }
  }
  return documentStartPos(editor);
}

function measureConfirmationTop(editor: Editor, shell: HTMLDivElement, anchorPos: number): number {
  const shellRect = shell.getBoundingClientRect();
  try {
    const coords = editor.view.coordsAtPos(anchorPos);
    return coords.top - shellRect.top + shell.scrollTop;
  } catch {
    return shell.scrollTop;
  }
}

export function DocumentEditorConfirmations({
  confirmations,
  disabled = false,
  editor,
  highlightedConfirmationId = null,
  onApprove,
  onReject,
  shellRef,
}: DocumentEditorConfirmationsProps) {
  const [positions, setPositions] = useState<PositionedConfirmation[]>([]);
  const anchorCacheRef = useRef<Map<string, number>>(new Map());
  const schedulePositionRefreshRef = useRef(createAnimationFrameScheduler());

  const sortedConfirmations = useMemo(
    () =>
      [...confirmations].sort((left, right) =>
        (left.created_at ?? "").localeCompare(right.created_at ?? ""),
      ),
    [confirmations],
  );

  function resolveCachedAnchorPos(editor: Editor, confirmation: Confirmation): number {
    const cached = anchorCacheRef.current.get(confirmation.id);
    if (cached !== undefined) {
      return cached;
    }
    const anchorPos = resolveAnchorPos(editor, confirmation);
    anchorCacheRef.current.set(confirmation.id, anchorPos);
    return anchorPos;
  }

  useLayoutEffect(() => {
    anchorCacheRef.current.clear();
    if (sortedConfirmations.length === 0) {
      setPositions([]);
      return;
    }

    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    const nextPositions = sortedConfirmations.map((confirmation) => {
      const anchorPos = resolveCachedAnchorPos(editor, confirmation);
      return {
        confirmation,
        top: measureConfirmationTop(editor, shell, anchorPos),
      };
    });
    setPositions(nextPositions);
  }, [editor, shellRef, sortedConfirmations]);

  useEffect(() => {
    const scheduleRefresh = schedulePositionRefreshRef.current;
    const refresh = () => {
      const shell = shellRef.current;
      if (!shell) {
        return;
      }
      anchorCacheRef.current.clear();
      setPositions(
        sortedConfirmations.map((confirmation) => {
          const anchorPos = resolveCachedAnchorPos(editor, confirmation);
          return {
            confirmation,
            top: measureConfirmationTop(editor, shell, anchorPos),
          };
        }),
      );
    };
    const schedule = () => scheduleRefresh(refresh);
    editor.on("update", schedule);
    window.addEventListener("resize", schedule);
    return () => {
      editor.off("update", schedule);
      window.removeEventListener("resize", schedule);
      scheduleRefresh.cancel();
    };
  }, [editor, shellRef, sortedConfirmations]);

  if (positions.length === 0) {
    return null;
  }

  return (
    <div
      aria-label="正文待确认写入"
      className="document-inline-confirmation-layer"
      data-testid="document-inline-confirmation-layer"
    >
      {positions.map(({ confirmation, top }) => (
        <div
          key={confirmation.id}
          className={`document-inline-confirmation-anchor${
            highlightedConfirmationId === confirmation.id
              ? " document-inline-confirmation-anchor--highlighted"
              : ""
          }`}
          data-testid={`inline-confirmation-${confirmation.id}`}
          style={{ top }}
        >
          <div className="document-inline-confirmation-card">
            <div className="document-inline-confirmation-card-header">
              <Space size={8} wrap>
                <Tag color="processing">待确认</Tag>
                <span className="document-inline-confirmation-card-title">
                  {confirmationActionLabel(confirmation.action_type)}
                </span>
              </Space>
            </div>
            <Typography.Text className="document-inline-confirmation-chapter" type="secondary">
              {confirmation.chapter_title ? `章节：${confirmation.chapter_title}` : "未关联章节"}
            </Typography.Text>
            <Typography.Paragraph className="document-inline-confirmation-preview">
              {confirmation.before_text?.trim()
                ? `原内容：${confirmation.before_text.trim()}`
                : confirmation.after_text?.trim() || "Agent 建议写入正文"}
            </Typography.Paragraph>
            <ConfirmationDiffView confirmation={confirmation} />
            <Space size={6}>
              <Button
                data-testid={`inline-confirmation-approve-${confirmation.id}`}
                disabled={disabled}
                onClick={() => onApprove(confirmation.id)}
                size="small"
                type="primary"
              >
                确认写入
              </Button>
              <Button
                data-testid={`inline-confirmation-reject-${confirmation.id}`}
                disabled={disabled}
                onClick={() => onReject(confirmation.id)}
                size="small"
              >
                拒绝
              </Button>
            </Space>
          </div>
        </div>
      ))}
    </div>
  );
}
