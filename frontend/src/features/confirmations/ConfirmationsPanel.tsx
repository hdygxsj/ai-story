import { Empty, Space, Tag, Typography } from "antd";
import { useMemo } from "react";

import type { Confirmation } from "../../api/confirmations";
import { ConfirmationActionCard } from "./ConfirmationActionCard";
import { ConfirmationHistoryCard } from "./ConfirmationHistoryCard";
import { pendingConfirmations } from "./confirmationPresentation";

type ConfirmationsPanelProps = {
  confirmationCount: number;
  confirmationHistory: Confirmation[];
  confirmations: Confirmation[];
  onApprove: (confirmationId: string) => void;
  onLocate?: (confirmation: Confirmation) => void;
  onReject: (confirmationId: string) => void;
};

export function ConfirmationsPanel({
  confirmationCount,
  confirmationHistory,
  confirmations,
  onApprove,
  onLocate,
  onReject,
}: ConfirmationsPanelProps) {
  const pendingReviewConfirmations = useMemo(() => pendingConfirmations(confirmations), [confirmations]);

  return (
    <div data-testid="confirmations-panel">
      <Typography.Title level={3} style={{ marginBottom: 8 }}>
        确认
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        正文写入请在对应章节的编辑器里确认；这里汇总待办，并保留你已处理的确认记录。
      </Typography.Paragraph>

      <Space direction="vertical" size={16} style={{ marginTop: 16, width: "100%" }}>
        <section data-testid="confirmations-pending-section">
          <Space align="center" style={{ marginBottom: 10 }}>
            <Typography.Text strong>待确认</Typography.Text>
            <Tag color="gold">{confirmationCount} 条</Tag>
          </Space>
          {pendingReviewConfirmations.length === 0 ? (
            <Empty description="没有待确认操作，可在章节树中查看带标记的章节" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {pendingReviewConfirmations.map((confirmation) => (
                <ConfirmationActionCard
                  key={confirmation.id}
                  confirmation={confirmation}
                  onApprove={onApprove}
                  onLocate={onLocate}
                  onReject={onReject}
                />
              ))}
            </Space>
          )}
        </section>

        <section data-testid="confirmations-history-section">
          <Space align="center" style={{ marginBottom: 10 }}>
            <Typography.Text strong>确认记录</Typography.Text>
            <Tag>{confirmationHistory.length} 条</Tag>
          </Space>
          {confirmationHistory.length === 0 ? (
            <Empty description="还没有确认记录，批准或拒绝写入后会显示在这里" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {confirmationHistory.map((confirmation) => (
                <ConfirmationHistoryCard key={confirmation.id} confirmation={confirmation} />
              ))}
            </Space>
          )}
        </section>
      </Space>
    </div>
  );
}
