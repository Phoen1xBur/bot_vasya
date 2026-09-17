// API client: attaches Authorization header from Telegram initData to all fetch calls
import { getInitData } from "../lib/telegram";

/** Human-readable FastAPI / validation error detail (string | object | array). */
export function formatApiDetail(detail: unknown): string {
  if (detail == null || detail === "") return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const rec = item as Record<string, unknown>;
          const loc = Array.isArray(rec.loc) ? rec.loc.filter((x) => x !== "body" && x !== "query").join(".") : "";
          const msg = typeof rec.msg === "string" ? rec.msg : JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .filter(Boolean)
      .join("; ");
  }
  if (typeof detail === "object") {
    const rec = detail as Record<string, unknown>;
    if ("detail" in rec) return formatApiDetail(rec.detail);
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }
  return String(detail);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    const msg = formatApiDetail(detail) || `HTTP ${status}`;
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

function authHeader(): { name: string; value: string } {
  return { name: "X-Telegram-Init-Data", value: getInitData() };
}

async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    params?: Record<string, string | number | null | undefined>;
  } = {}
): Promise<T> {
  const { method = "GET", body, params } = options;
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  const { name: authName, value: authValue } = authHeader();
  const headers: Record<string, string> = {
    [authName]: authValue,
  };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 204) return undefined as T;
  let data: unknown;
  const ct = resp.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    data = await resp.json();
  } else {
    data = await resp.text();
  }
  if (!resp.ok) {
    const detail =
      data && typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | null | undefined>) =>
    request<T>(path, { method: "GET", params }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body }),
  // ---- User ----
  getBalance: (chatId?: number | null) =>
    api.get<{ money: number; vasya_coin: string; chat_id: number }>(
      `/api/user/balance${chatId ? `?chat_id=${chatId}` : ""}`
    ),
  getProfile: (chatId?: number | null) =>
    api.get<import("../types").UserProfile>("/api/user/profile", {
      chat_id: chatId ?? undefined,
    }),
  getMySubscription: () =>
    api.get<import("../types").SubscriptionInfo>("/api/subscriptions/me"),
  cancelAutoRenew: () =>
    api.post<{ ok: boolean; subscription: import("../types").SubscriptionInfo | null }>(
      "/api/subscriptions/cancel_auto_renew"
    ),
  resumeAutoRenew: () =>
    api.post<{ ok: boolean; subscription: import("../types").SubscriptionInfo | null }>(
      "/api/subscriptions/resume_auto_renew"
    ),
  // ---- Games ----
  createRoom: (body: { game_type: string; chat_id: number | null; target_id?: number; bet?: number }) =>
    api.post<import("../types").RoomState>("/api/games/rooms", body),
  getRoom: (roomId: string) =>
    api.get<import("../types").RoomState>(`/api/games/rooms/${roomId}`),
  joinRoom: (roomId: string, body?: { bet?: number }) =>
    api.post<import("../types").RoomState>(`/api/games/rooms/${roomId}/join`, body),
  roomAction: (roomId: string, action: unknown) =>
    api.post<unknown>(`/api/games/rooms/${roomId}/action`, { action }),
  cancelRoom: (roomId: string) =>
    api.post<{ ok: boolean; status: string }>(`/api/games/rooms/${roomId}/cancel`),
  // ---- Ads ----
  getAdRules: () =>
    api.get<import("../types").AdRules>("/api/ads/rules"),
  submitCampaign: (body: { text: string; link: string; target_unique_users: number; contact: string; rules_accepted: boolean }) =>
    api.post<import("../types").AdCampaignResponse>("/api/ads/campaigns", body),
  getCampaigns: (status?: string) =>
    api.get<{ campaigns: import("../types").AdCampaign[] }>("/api/ads/campaigns", { status }),
  approveCampaign: (id: string, comment: string) =>
    api.post<{ ok: boolean; campaign_id: string; selected_chats: number[]; actual_unique_users: number; within_tolerance: boolean }>(
      `/api/ads/campaigns/${id}/approve`, { comment }),
  rejectCampaign: (id: string, comment: string) =>
    api.post<{ ok: boolean; campaign_id: string }>(`/api/ads/campaigns/${id}/reject`, { comment }),
  // ---- Admin ----
  getAdminStats: () =>
    api.get<import("../types").AdminStats>("/api/admin/stats"),
  getPrices: () =>
    api.get<import("../types").AdminPrices>("/api/admin/prices"),
  setPrices: (body: Partial<import("../types").AdminPrices>) =>
    api.post<{ ok: boolean }>("/api/admin/prices", body),
  getPayments: (limit = 50) =>
    api.get<{ payments: import("../types").Payment[] }>("/api/admin/payments", { limit }),

  getUserSettings: (chatId: number) =>
    api.get<{ chat_id: number; can_tag: boolean; money: number; member_status: string }>(
      "/api/user/settings",
      { chat_id: chatId }
    ),
  toggleTag: (chatId: number) =>
    api.post<{ chat_id: number; can_tag: boolean; ok: boolean }>("/api/user/settings/toggle_tag", {
      chat_id: chatId,
    }),
  getMyChats: () =>
    api.get<{ chats: Array<{
      chat_id: number;
      answer_chance: number;
      ai_generate_text: boolean;
      member_status: string;
      can_tag: boolean;
      money: number;
    }> }>("/api/chats/mine"),
  patchChatSettings: (chatId: number, body: { answer_chance?: number; ai_generate_text?: boolean }) =>
    request<{ chat_id: number; answer_chance: number; ai_generate_text: boolean; ok: boolean }>(
      `/api/chats/${chatId}/settings`,
      { method: "PATCH", body }
    ),
  initPayment: (body: Record<string, unknown>) =>
    api.post<{ order_id: string; payment_url: string; amount: number }>("/api/payments/init", body),
  getAdminSubscriptions: () =>
    api.get<{ subscriptions: import("../types").AdminSubscription[] }>("/api/admin/subscriptions"),
  cancelRefundSubscription: (subId: number) =>
    api.post<{ ok: boolean; refund_skipped?: string | null }>(
      `/api/admin/subscriptions/${subId}/cancel_refund`,
      { confirm: true }
    ),
  getAdminCampaigns: () =>
    api.get<{ campaigns: import("../types").AdCampaign[] }>("/api/admin/campaigns"),
  grantSubscription: (body: {
    user_id?: number;
    username?: string;
    tier: string;
    days?: number;
    expires_at?: string;
  }) =>
    api.post<{
      ok: boolean;
      user_id: number;
      username?: string | null;
      tier: string;
      expires_at: string | null;
    }>("/api/admin/grant/subscription", body),
  grantCoins: (body: {
    user_id?: number;
    username?: string;
    chat_id: number;
    amount: number;
  }) =>
    api.post<{
      ok: boolean;
      user_id: number;
      username?: string | null;
      chat_id: number;
      amount: number;
      balance: number | null;
    }>("/api/admin/grant/coins", body),
};
