const lastDocumentStorageKey = "ai-story-workspace-last-document";
const lastConversationStorageKey = "ai-story-workspace-last-conversation";

function readStorageMap(key: string): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return {};
    }
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return parsed as Record<string, string>;
  } catch {
    return {};
  }
}

function writeStorageMap(key: string, map: Record<string, string>) {
  window.localStorage.setItem(key, JSON.stringify(map));
}

export function getStoredDocumentId(novelId: string): string | null {
  return readStorageMap(lastDocumentStorageKey)[novelId] ?? null;
}

export function setStoredDocumentId(novelId: string, documentId: string | null) {
  const map = readStorageMap(lastDocumentStorageKey);
  if (documentId) {
    map[novelId] = documentId;
  } else {
    delete map[novelId];
  }
  writeStorageMap(lastDocumentStorageKey, map);
}

export function getStoredConversationId(novelId: string): string | null {
  return readStorageMap(lastConversationStorageKey)[novelId] ?? null;
}

export function setStoredConversationId(novelId: string, conversationId: string | null) {
  const map = readStorageMap(lastConversationStorageKey);
  if (conversationId) {
    map[novelId] = conversationId;
  } else {
    delete map[novelId];
  }
  writeStorageMap(lastConversationStorageKey, map);
}
