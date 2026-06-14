import { Button, Flex, Space, Typography } from "antd";

import type { Confirmation } from "../../api/confirmations";
import { ConfirmationDiffView } from "./ConfirmationDiffView";
import { confirmationActionLabel } from "./confirmationPresentation";

type ConfirmationActionCardProps = {
  confirmation: Confirmation;
  disabled?: boolean;
  onApprove: (confirmationId: string) => void;
  onLocate?: (confirmation: Confirmation) => void;
  onReject: (confirmationId: string) => void;
};

export function ConfirmationActionCard({
  confirmation,
  disabled = false,
  onApprove,
  onLocate,
  onReject,
}: ConfirmationActionCardProps) {
  return (
    <div
      aria-label="Agent 正文写入确认"
      data-testid="agent-write-confirmation"
      style={{
        background: "#f0fdf4",
        border: "1px solid rgba(34,197,94,0.28)",
        borderRadius: 16,
        flexShrink: 0,
        padding: 12,
      }}
    >
      <Flex align="flex-start" justify="space-between" gap={12} wrap="wrap">
        <Space direction="vertical" size={10} style={{ flex: 1, minWidth: 0 }}>
          <Space direction="vertical" size={4}>
            <Typography.Text strong>正文写入待确认</Typography.Text>
            <Typography.Text type="secondary">{confirmationActionLabel(confirmation.action_type)}</Typography.Text>
          </Space>
          <ConfirmationDiffView confirmation={confirmation} />
        </Space>
        <Space wrap>
          {onLocate && confirmation.document_id ? (
            <Button
              data-testid={`confirmation-locate-${confirmation.id}`}
              disabled={disabled}
              onClick={() => onLocate(confirmation)}
              size="small"
            >
              定位正文
            </Button>
          ) : null}
          <Button disabled={disabled} size="small" type="primary" onClick={() => onApprove(confirmation.id)}>
            写入正文
          </Button>
          <Button disabled={disabled} size="small" onClick={() => onReject(confirmation.id)}>
            拒绝
          </Button>
        </Space>
      </Flex>
    </div>
  );
}
