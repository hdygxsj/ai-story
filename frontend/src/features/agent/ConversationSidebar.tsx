import { DeleteOutlined, EditOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Input, Modal, Popconfirm, Typography } from "antd";
import { useState } from "react";

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

  return (
    <div
      data-testid="agent-conversation-sidebar"
      style={{
        borderRight: "1px solid rgba(15,23,42,0.08)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        minHeight: 0,
        width: 148,
      }}
    >
      <Button
        block
        disabled={disabled}
        icon={<PlusOutlined />}
        onClick={onCreateConversation}
        size="small"
        style={{ flexShrink: 0, margin: "0 8px 8px" }}
        type="default"
      >
        新对话
      </Button>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto", padding: "0 8px 8px" }}>
        {conversations.map((conversation) => {
          const active = conversation.id === activeConversationId;
          return (
            <div
              key={conversation.id}
              style={{
                alignItems: "center",
                background: active ? "rgba(99,91,255,0.10)" : "transparent",
                borderRadius: 10,
                display: "flex",
                gap: 4,
                marginBottom: 4,
                padding: "6px 8px",
              }}
            >
              <button
                aria-current={active ? "true" : undefined}
                disabled={disabled}
                onClick={() => onSelectConversation(conversation.id)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#111827",
                  cursor: disabled ? "not-allowed" : "pointer",
                  flex: 1,
                  fontSize: 12,
                  padding: 0,
                  textAlign: "left",
                }}
                type="button"
              >
                <Typography.Text ellipsis style={{ maxWidth: 96 }}>
                  {conversation.title}
                </Typography.Text>
              </button>
              <Button
                aria-label={`重命名对话 ${conversation.title}`}
                disabled={disabled}
                icon={<EditOutlined />}
                onClick={() => openRename(conversation.id, conversation.title)}
                size="small"
                type="text"
              />
              <Popconfirm
                cancelText="取消"
                disabled={disabled}
                okText="删除"
                onConfirm={() => onDeleteConversation(conversation.id)}
                title="删除这个对话？"
              >
                <Button
                  aria-label={`删除对话 ${conversation.title}`}
                  disabled={disabled}
                  icon={<DeleteOutlined />}
                  size="small"
                  type="text"
                />
              </Popconfirm>
            </div>
          );
        })}
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
      <Button
        block
        disabled={disabled}
        icon={<SettingOutlined />}
        onClick={onOpenContextSettings}
        size="small"
        style={{ flexShrink: 0, margin: "0 8px 8px" }}
        type="text"
      >
        上下文设置
      </Button>
    </div>
  );
}
