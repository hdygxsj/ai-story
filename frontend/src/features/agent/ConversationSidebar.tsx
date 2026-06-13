import { DeleteOutlined, EditOutlined, MoreOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Dropdown, Input, Modal, Select } from "antd";
import type { MenuProps } from "antd";
import { useMemo, useState } from "react";

import type { Conversation } from "../../api/conversations";

type ConversationSidebarProps = {
  conversations: Conversation[];
  activeConversationId: string | null;
  disabled?: boolean;
  onCreateConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
  onOpenContextSettings: () => void;
  onRenameConversation: (conversationId: string, title: string) => void;
  onSelectConversation: (conversationId: string) => void;
};

export function ConversationSidebar({
  conversations,
  activeConversationId,
  disabled = false,
  onCreateConversation,
  onDeleteConversation,
  onOpenContextSettings,
  onRenameConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  function openRename(conversationId: string, title: string) {
    setRenamingId(conversationId);
    setRenameTitle(title);
  }

  function submitRename() {
    if (!renamingId || !renameTitle.trim()) {
      setRenamingId(null);
      return;
    }
    onRenameConversation(renamingId, renameTitle.trim());
    setRenamingId(null);
  }

  const conversationMenuItems = useMemo<MenuProps["items"]>(() => {
    if (!activeConversation) {
      return [];
    }
    return [
      {
        key: "rename",
        icon: <EditOutlined />,
        label: "重命名",
        onClick: () => openRename(activeConversation.id, activeConversation.title),
      },
      {
        key: "delete",
        danger: true,
        icon: <DeleteOutlined />,
        label: "删除对话",
        onClick: () => {
          Modal.confirm({
            cancelText: "取消",
            content: "删除后无法恢复该对话历史。",
            okText: "删除",
            okType: "danger",
            onOk: () => onDeleteConversation(activeConversation.id),
            title: "删除这个对话？",
          });
        },
      },
    ];
  }, [activeConversation, disabled, onDeleteConversation]);

  return (
    <div className="agent-panel-toolbar" data-testid="agent-conversation-sidebar">
      <div className="agent-panel-toolbar-row">
        <Select
          allowClear={false}
          className="agent-panel-toolbar-select"
          disabled={disabled || conversations.length === 0}
          optionFilterProp="label"
          options={conversations.map((conversation) => ({
            label: conversation.title,
            value: conversation.id,
          }))}
          placeholder="暂无对话"
          showSearch={conversations.length > 4}
          size="small"
          value={activeConversationId ?? undefined}
          onChange={(value) => onSelectConversation(value)}
        />
        <Button
          aria-label="创建对话"
          disabled={disabled}
          icon={<PlusOutlined />}
          onClick={onCreateConversation}
          size="small"
          type="default"
        />
        <Dropdown disabled={disabled || !activeConversation} menu={{ items: conversationMenuItems }} trigger={["click"]}>
          <Button aria-label="对话操作" disabled={disabled || !activeConversation} icon={<MoreOutlined />} size="small" type="text" />
        </Dropdown>
        <Button
          aria-label="上下文设置"
          disabled={disabled}
          icon={<SettingOutlined />}
          onClick={onOpenContextSettings}
          size="small"
          type="text"
        />
      </div>
      <Modal
        cancelText="取消"
        okText="保存"
        onCancel={() => setRenamingId(null)}
        onOk={submitRename}
        open={renamingId !== null}
        title="重命名对话"
      >
        <Input value={renameTitle} onChange={(event) => setRenameTitle(event.target.value)} />
      </Modal>
    </div>
  );
}
