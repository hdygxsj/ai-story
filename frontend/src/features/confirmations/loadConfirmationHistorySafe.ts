import type { Confirmation } from "../../api/confirmations";
import { listConfirmationHistory } from "../../api/confirmations";

export async function loadConfirmationHistorySafe(
  token: string,
  novelId: string,
): Promise<Confirmation[]> {
  try {
    return await listConfirmationHistory(token, novelId);
  } catch {
    return [];
  }
}
