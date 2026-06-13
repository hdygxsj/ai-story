import { DeleteOutlined, EditOutlined, HistoryOutlined, MoreOutlined, PlusOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Dropdown, Empty, Input, Modal } from "antd";
import type { MenuProps } from "antd";
import { useMemo, useState } from "react";

import type { Conversation } from "../../api/conversations";
import {
  formatConversationTime,
  getConversationSubtitle,
  getConversationTooltip,
} from "./conversationPresentation";

type ConversationSidebarProps = {
  conversations: Conversation[];
  activeConversationId: string | null;
  disabled?: boolean;
  variant?: "default" | "header";
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
  variant = "default",
  onCreateConversation,
  onDeleteConversation,
  onOpenContextSettings,
  onRenameConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [searchValue, setSearchValue] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  const filteredConversations = useMemo(() => {
    const keyword = searchValue.trim().toLowerCase();
    if (!keyword) {
      return conversations;
    }
    return conversations.filter((conversation) => {
      const haystack = [conversation.title, conversation.preview ?? ""].join(" ").toLowerCase();
      return haystack.includes(keyword);
    });
  }, [conversations, searchValue]);

  function handleSelectConversation(conversationId: string) {
    onSelectConversation(conversationId);
    setHistoryOpen(false);
    setSearchValue("");
  }

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
    <div
      className={`agent-panel-toolbar${variant === "header" ? " agent-panel-toolbar-header" : ""}`}
      data-testid="agent-conversation-sidebar"
    >
      <div className="agent-panel-toolbar-row">
        <Dropdown
          disabled={disabled}
          onOpenChange={(open) => {
            setHistoryOpen(open);
            if (!open) {
              setSearchValue("");
            }
          }}
          open={historyOpen}
          overlayClassName="agent-panel-history-overlay"
          popupRender={() => (
            <div className="agent-panel-history-dropdown" data-testid="agent-conversation-history-dropdown">
              {conversations.length > 4 ? (
                <Input
                  allowClear
                  aria-label="搜索历史对话"
                  placeholder="搜索对话"
                  size="small"
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                />
              ) : null}
              <div className="agent-panel-history-list">
                {filteredConversations.length === 0 ? (
                  <Empty description={conversations.length === 0 ? "暂无对话" : "没有匹配的对话"} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  filteredConversations.map((conversation) => (
                    <button
                      className={`agent-panel-history-item${conversation.id === activeConversationId ? " agent-panel-history-item-active" : ""}`}
                      key={conversation.id}
                      title={getConversationTooltip(conversation)}
                      type="button"
                      onClick={() => handleSelectConversation(conversation.id)}
                    >
                      <span className="agent-panel-history-item-main">
                        <span className="agent-panel-history-item-title">{conversation.title}</span>
                        <span className="agent-panel-history-item-time">{formatConversationTime(conversation.updated_at)}</span>
                      </span>
                      <span className="agent-panel-history-item-preview">{getConversationSubtitle(conversation)}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
          trigger={["click"]}
        >
          <Button
            aria-label="历史对话"
            disabled={disabled || conversations.length === 0}
            icon={<HistoryOutlined />}
            size="small"
            title={activeConversation ? getConversationTooltip(activeConversation) : "历史对话"}
            type="text"
          />
        </Dropdown>
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
