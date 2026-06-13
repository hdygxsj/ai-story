import { apiRequest } from "./http";

export type Confirmation = {
  id: string;
  action_type: string;
  status: string;
  payload: Record<string, unknown>;
  document_id?: string | null;
  is_stale?: boolean;
  before_text?: string | null;
  after_text?: string | null;
};

export function listConfirmations(token: string, novelId: string) {
  return apiRequest<Confirmation[]>(`/novels/${novelId}/confirmations`, { token });
}

export function approveConfirmation(token: string, confirmationId: string) {
  return apiRequest<Confirmation>(`/confirmations/${confirmationId}/approve`, {
    method: "POST",
    token,
  });
}

export function rejectConfirmation(token: string, confirmationId: string) {
  return apiRequest<Confirmation>(`/confirmations/${confirmationId}/reject`, {
    method: "POST",
    token,
  });
}
