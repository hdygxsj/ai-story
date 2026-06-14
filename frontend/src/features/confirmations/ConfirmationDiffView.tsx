import { Space, Tag, Typography } from "antd";
import { memo, useMemo } from "react";

import type { Confirmation } from "../../api/confirmations";
import { diffText, hasDiffChanges, type DiffDisplaySegment } from "./textDiff";

type ConfirmationDiffViewProps = {
  confirmation: Confirmation;
};

function renderSegment(segment: DiffDisplaySegment, index: number) {
  if (segment.kind === "equal") {
    return (
      <div
        key={`equal-${index}`}
        style={{
          color: "#6b7280",
          marginBottom: 8,
          whiteSpace: "pre-wrap",
        }}
      >
        {segment.text}
      </div>
    );
  }

  if (segment.kind === "insert") {
    return (
      <div
        key={`insert-${index}`}
        data-testid="confirmation-diff-insert"
        style={{
          background: "#dcfce7",
          borderLeft: "3px solid #22c55e",
          borderRadius: 8,
          color: "#166534",
          marginBottom: 8,
          padding: "8px 10px",
          whiteSpace: "pre-wrap",
        }}
      >
        <Typography.Text strong style={{ color: "#15803d", display: "block", fontSize: 12, marginBottom: 4 }}>
          新增
        </Typography.Text>
        {segment.text}
      </div>
    );
  }

  if (segment.kind === "delete") {
    return (
      <div
        key={`delete-${index}`}
        data-testid="confirmation-diff-delete"
        style={{
          background: "#fee2e2",
          borderLeft: "3px solid #ef4444",
          borderRadius: 8,
          color: "#991b1b",
          marginBottom: 8,
          padding: "8px 10px",
          textDecoration: "line-through",
          whiteSpace: "pre-wrap",
        }}
      >
        <Typography.Text strong style={{ color: "#b91c1c", display: "block", fontSize: 12, marginBottom: 4 }}>
          删除
        </Typography.Text>
        {segment.text}
      </div>
    );
  }

  return (
    <div
      key={`modify-${index}`}
      data-testid="confirmation-diff-modify"
      style={{
        background: "#ffedd5",
        borderLeft: "3px solid #f97316",
        borderRadius: 8,
        marginBottom: 8,
        padding: "8px 10px",
      }}
    >
      <Typography.Text strong style={{ color: "#c2410c", display: "block", fontSize: 12, marginBottom: 6 }}>
        修改
      </Typography.Text>
      <div
        style={{
          background: "#fee2e2",
          borderRadius: 6,
          color: "#991b1b",
          marginBottom: 6,
          padding: "6px 8px",
          textDecoration: "line-through",
          whiteSpace: "pre-wrap",
        }}
      >
        {segment.before}
      </div>
      <div
        style={{
          background: "#dcfce7",
          borderRadius: 6,
          color: "#166534",
          padding: "6px 8px",
          whiteSpace: "pre-wrap",
        }}
      >
        {segment.after}
      </div>
    </div>
  );
}

export const ConfirmationDiffView = memo(function ConfirmationDiffView({ confirmation }: ConfirmationDiffViewProps) {
  const before = confirmation.before_text ?? "";
  const after = confirmation.after_text ?? "";
  const segments = useMemo(() => diffText(before, after), [before, after]);

  if (!before && !after) {
    return (
      <Typography.Text data-testid="confirmation-diff-empty" type="secondary">
        暂无可展示的文本差异。
      </Typography.Text>
    );
  }

  if (!hasDiffChanges(segments)) {
    return (
      <Typography.Text data-testid="confirmation-diff-empty" type="secondary">
        本次写入未检测到文本变化。
      </Typography.Text>
    );
  }

  return (
    <div data-testid="confirmation-diff-view">
      <Space size={8} style={{ marginBottom: 10 }} wrap>
        <Tag color="success">新增</Tag>
        <Tag color="error">删除</Tag>
        <Tag color="warning">修改</Tag>
      </Space>
      <div
        style={{
          maxHeight: 280,
          overflow: "auto",
        }}
      >
        {segments.map((segment, index) => renderSegment(segment, index))}
      </div>
    </div>
  );
});
