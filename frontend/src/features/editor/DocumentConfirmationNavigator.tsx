import { Button, Space, Typography } from "antd";

type DocumentConfirmationNavigatorProps = {
  activeIndex: number;
  onSelect: (index: number) => void;
  total: number;
};

export function DocumentConfirmationNavigator({
  activeIndex,
  onSelect,
  total,
}: DocumentConfirmationNavigatorProps) {
  if (total <= 1) {
    return null;
  }

  return (
    <div className="document-confirmation-navigator" data-testid="document-confirmation-navigator">
      <Typography.Text className="document-confirmation-navigator-label" type="secondary">
        {total} 处待确认
      </Typography.Text>
      <Space size={4} wrap>
        {Array.from({ length: total }, (_, index) => (
          <Button
            key={index}
            aria-label={`定位到第 ${index + 1} 处待确认`}
            data-testid={`document-confirmation-nav-${index + 1}`}
            onClick={() => onSelect(index)}
            size="small"
            type={index === activeIndex ? "primary" : "default"}
          >
            {index + 1}
          </Button>
        ))}
      </Space>
    </div>
  );
}
