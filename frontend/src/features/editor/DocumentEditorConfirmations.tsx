import { Button, Space, Typography } from "antd";
import type { Editor } from "@tiptap/react";
import type { RefObject } from "react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { Confirmation } from "../../api/confirmations";
import { createAnimationFrameScheduler } from "../../utils/schedule";
import { confirmationAnchorText } from "../confirmations/confirmationLocation";
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

    const shellRect = shell.getBoundingClientRect();
    const nextPositions = sortedConfirmations.map((confirmation) => {
      const anchorPos = resolveCachedAnchorPos(editor, confirmation);
      const coords = editor.view.coordsAtPos(anchorPos);
      return {
        confirmation,
        top: coords.top - shellRect.top + shell.scrollTop,
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
      const shellRect = shell.getBoundingClientRect();
      setPositions(
        sortedConfirmations.map((confirmation) => {
          const anchorPos = resolveCachedAnchorPos(editor, confirmation);
          const coords = editor.view.coordsAtPos(anchorPos);
          return {
            confirmation,
            top: coords.top - shellRect.top + shell.scrollTop,
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
              <span className="document-inline-confirmation-card-title">待确认写入</span>
            </div>
            <Typography.Paragraph className="document-inline-confirmation-preview">
              {confirmation.after_text?.trim() || "Agent 建议写入正文"}
            </Typography.Paragraph>
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
