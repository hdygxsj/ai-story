import type { Conversation } from "../../api/conversations";

export function formatConversationTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  const sameYear = date.getFullYear() === now.getFullYear();
  return new Intl.DateTimeFormat("zh-CN", {
    ...(sameYear ? {} : { year: "numeric" }),
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    month: "numeric",
  }).format(date);
}

export function getConversationSubtitle(conversation: Conversation): string {
  if (conversation.preview?.trim()) {
    return conversation.preview.trim();
  }
  if ((conversation.message_count ?? 0) > 0) {
    return "暂无预览";
  }
  return "尚未开始对话";
}

export function getConversationTooltip(conversation: Conversation): string {
  return `${conversation.title} · ${formatConversationTime(conversation.updated_at)}`;
}
