// Type definitions for API responses

export interface UserProfile {
  user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  money: number;
  vasya_coin: string;
  chat_id: number | null;
}

export interface SubscriptionInfo {
  tier: string;
  tag: string;
  status: string;
  expires_at: string | null;
  auto_renew: boolean;
  has_recurring_key: boolean;
  limits_multiplier: number;
  work_bonus: number;
  free_jail_per_day: number;
  ai_daily_limit: number;
}

export interface RoomState {
  id: string;
  game_type: string;
  chat_id: number;
  initiator_id: number;
  target_id: number | null;
  status: string;
  state: Record<string, unknown> | null;
  bet: number;
  winner_id: number | null;
  created_at: string | null;
  expires_at: string | null;
}

export interface TTTActionResponse {
  board: string;
  turn: string | null;
  winner: number | null;
  status: string;
}

export interface RouletteSpinResult {
  number: number;
  color: string;
  results: Array<{ user_id: number; bet: number; won: number; won_net: number }>;
}

export interface SlotsSpinResult {
  reels: string[];
  won: number;
  bet: number;
  net: number;
}

export interface AdRules {
  rules: string[];
  total_unique_users: number;
  /** kopecks per 1000 unique users (from Redis / defaults) */
  price_per_1000?: number;
}

export interface AdCampaign {
  id: string;
  campaign_id?: string;
  advertiser_id: number;
  text: string;
  link: string;
  target_unique_users: number;
  price: number;
  status: string;
  ai_verdict: Record<string, unknown> | null;
  admin_comment: string | null;
  contact: string;
  selected_chats?: number[] | null;
  actual_reach?: number | null;
  created_at: string | null;
  sent_at: string | null;
  price_is_estimate?: boolean;
  can_pay?: boolean;
}

export interface AdCampaignResponse {
  campaign_id: string;
  status: string;
  ai_verdict: Record<string, unknown> | null;
  price: number;
  text?: string;
  link?: string;
  admin_comment?: string | null;
  price_is_estimate?: boolean;
  can_pay?: boolean;
}

export interface AdminStats {
  revenue_kopecks: number;
  active_subscriptions: number;
  total_donations_kopecks: number;
  ad_campaigns_by_status: Record<string, number>;
  economy_balance: unknown;
}

export interface AdminPrices {
  sub_vip: string | number;
  sub_premium: string | number;
  sub_elite: string | number;
  ad_per_1000: string | number;
  ai_check_enabled: string;
}

export interface Payment {
  order_id: string;
  user_id: number;
  amount: number;
  payment_type: string;
  status: string;
  fulfilled: boolean;
  created_at: string | null;
}


export interface AdminSubscription {
  id: number;
  user_id: number;
  username: string | null;
  first_name: string | null;
  tier: string;
  status: string;
  auto_renew: boolean;
  has_recurring_key: boolean;
  started_at: string | null;
  expires_at: string | null;
  payment: {
    order_id: string;
    payment_id: string | null;
    amount: number;
    status: string;
    created_at: string | null;
  } | null;
}

export interface AdminChat {
  chat_id: number;
  answer_chance: number;
  ai_generate_text: boolean;
  member_status: string;
  can_tag: boolean;
  money: number;
}
