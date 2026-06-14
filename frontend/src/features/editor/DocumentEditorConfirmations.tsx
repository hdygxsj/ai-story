import { Button, Space, Typography } from "antd";
import type { Editor } from "@tiptap/react";
import type { RefObject } from "react";
import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import type { Confirmation } from "../../api/confirmations";
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

  const sortedConfirmations = useMemo(
    () =>
      [...confirmations].sort((left, right) =>
        (left.created_at ?? "").localeCompare(right.created_at ?? ""),
      ),
    [confirmations],
  );

  useLayoutEffect(() => {
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
      const anchorPos = resolveAnchorPos(editor, confirmation);
      const coords = editor.view.coordsAtPos(anchorPos);
      return {
        confirmation,
        top: coords.top - shellRect.top + shell.scrollTop,
      };
    });
    setPositions(nextPositions);
  }, [editor, shellRef, sortedConfirmations]);

  useEffect(() => {
    const refresh = () => {
      const shell = shellRef.current;
      if (!shell) {
        return;
      }
      const shellRect = shell.getBoundingClientRect();
      setPositions((current) =>
        current.map((item) => {
          const anchorPos = resolveAnchorPos(editor, item.confirmation);
          const coords = editor.view.coordsAtPos(anchorPos);
          return {
            ...item,
            top: coords.top - shellRect.top + shell.scrollTop,
          };
        }),
      );
    };
    editor.on("update", refresh);
    window.addEventListener("resize", refresh);
    return () => {
      editor.off("update", refresh);
      window.removeEventListener("resize", refresh);
    };
  }, [editor, shellRef]);

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
