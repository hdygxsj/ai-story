import { Space, Tag, Typography } from "antd";

import type { Confirmation } from "../../api/confirmations";
import { ConfirmationDiffView } from "./ConfirmationDiffView";
import {
  confirmationActionLabel,
  confirmationHistoryPreview,
  confirmationStatusLabel,
  formatConfirmationTime,
} from "./confirmationPresentation";

type ConfirmationHistoryCardProps = {
  confirmation: Confirmation;
};

export function ConfirmationHistoryCard({ confirmation }: ConfirmationHistoryCardProps) {
  const preview = confirmationHistoryPreview(confirmation);
  const resolvedAt = confirmation.resolved_at ?? confirmation.created_at;

  return (
    <div
      className="confirmation-history-card"
      data-testid="confirmation-history-card"
      style={{
        background: "#ffffff",
        border: "1px solid rgba(15,23,42,0.08)",
        borderRadius: 14,
        padding: "12px 14px",
      }}
    >
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Space align="start" style={{ justifyContent: "space-between", width: "100%" }} wrap>
          <Space direction="vertical" size={2}>
            <Space size={6} wrap>
              <Tag color={confirmation.status === "approved" ? "success" : "default"}>
                {confirmationStatusLabel(confirmation.status)}
              </Tag>
              <Typography.Text strong>{confirmationActionLabel(confirmation.action_type)}</Typography.Text>
            </Space>
            <Typography.Text type="secondary">
              {confirmation.chapter_title ? `章节：${confirmation.chapter_title}` : "未关联章节"}
            </Typography.Text>
          </Space>
          <Typography.Text style={{ fontSize: 12 }} type="secondary">
            {formatConfirmationTime(resolvedAt)}
          </Typography.Text>
        </Space>
        {preview ? (
          <Typography.Paragraph
            ellipsis={{ rows: 2 }}
            style={{ color: "#64748b", fontSize: 12, marginBottom: 0 }}
            type="secondary"
          >
            {preview}
          </Typography.Paragraph>
        ) : null}
        <ConfirmationDiffView confirmation={confirmation} />
      </Space>
    </div>
  );
}
