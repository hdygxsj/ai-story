export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const API_DETAIL_MESSAGES: Record<string, string> = {
  "Confirmation already resolved": "该确认项已处理。",
  "Document changed after this proposal was created":
    "该写入方案已自动失效，请让 Agent 基于最新正文重新生成。",
  "Selected text no longer has a unique editable match":
    "原文已变更，无法定位要替换的段落。请拒绝此方案后重新生成。",
};

export function formatApiErrorMessage(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return API_DETAIL_MESSAGES[parsed.detail] ?? parsed.detail;
    }
  } catch {
    // Keep the raw response when it is not JSON.
  }
  return raw;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(formatApiErrorMessage(message));
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}
