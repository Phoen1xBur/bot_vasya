// API client: attaches Authorization header from Telegram initData to all fetch calls
import { getInitData } from "../lib/telegram";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function authHeader(): string {
  return getInitData();
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
  const headers: Record<string, string> = {
    Authorization: authHeader(),
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
    throw new ApiError(resp.status, data);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | null | undefined>) =>
    request<T>(path, { method: "GET", params }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body }),
  // ---- User ----
  getProfile: (chatId: number | null) =>
    api.get<import("../types").UserProfile>("/api/user/profile", { chat_id: chatId }),
  getMySubscription: () =>
    api.get<import("../types").SubscriptionInfo>("/api/subscriptions/me"),
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
  getAdminCampaigns: () =>
    api.get<{ campaigns: import("../types").AdCampaign[] }>("/api/admin/campaigns"),
};
