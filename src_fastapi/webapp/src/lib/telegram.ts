// Telegram WebApp integration: init, theme, haptics, URL params

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string;
        initDataUnsafe: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
            photo_url?: string;
          };
        };
        colorScheme: "light" | "dark";
        themeParams: Record<string, string>;
        ready: () => void;
        expand: () => void;
        close: () => void;
        HapticFeedback: {
          impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
          notificationOccurred: (type: "error" | "success" | "warning") => void;
          selectionChanged: () => void;
        };
        BackButton: {
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
        setHeaderColor?: (color: string) => void;
        setBackgroundColor?: (color: string) => void;
      };
    };
  }
}

export type PageName =
  | "profile"
  | "ttt"
  | "roulette"
  | "slots"
  | "casino"
  | "advertise"
  | "admin"
  | "payment";

export interface UrlParams {
  page: PageName;
  chat_id: string | null;
  request_func: string | null;
  game: string | null;
  room: string | null;
  initiator: string | null;
  target: string | null;
}

export function getTelegramWebApp() {
  return window.Telegram?.WebApp;
}

export function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

export function getCurrentUserId(): number | null {
  return window.Telegram?.WebApp?.initDataUnsafe?.user?.id ?? null;
}

export function getUrlParams(): UrlParams {
  const u = new URLSearchParams(window.location.search);
  return {
    page: (u.get("page") as PageName) || "profile",
    chat_id: u.get("chat_id"),
    request_func: u.get("request_func"),
    game: u.get("game"),
    room: u.get("room"),
    initiator: u.get("initiator"),
    target: u.get("target"),
  };
}

export function initTelegram() {
  const tg = getTelegramWebApp();
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor?.("#0f0f1e");
      tg.setBackgroundColor?.("#0f0f1e");
    } catch {
      // ignore
    }
  }
}

export function applyTheme() {
  const tg = getTelegramWebApp();
  const scheme = tg?.colorScheme ?? "dark";
  const html = document.documentElement;
  if (scheme === "light") {
    html.classList.remove("dark");
    html.classList.add("light");
  } else {
    html.classList.remove("light");
    html.classList.add("dark");
  }
}

export function haptic(style: "light" | "medium" | "heavy" | "rigid" | "soft" = "medium") {
  try {
    getTelegramWebApp()?.HapticFeedback?.impactOccurred(style);
  } catch {
    // ignore
  }
}

export function hapticNotify(type: "error" | "success" | "warning") {
  try {
    getTelegramWebApp()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    // ignore
  }
}

export function hapticSelection() {
  try {
    getTelegramWebApp()?.HapticFeedback?.selectionChanged();
  } catch {
    // ignore
  }
}

export function isInsideTelegram(): boolean {
  const wa = window.Telegram?.WebApp;
  if (!wa) return false;
  // initData is empty outside a real Telegram WebApp session
  return Boolean(wa.initData && wa.initData.length > 0);
}

export function isTelegramOnlyPage(page: PageName, params: UrlParams): boolean {
  const gated: PageName[] = ["ttt", "roulette", "slots", "casino"];
  if (gated.includes(page)) return true;
  // any deep-link into a room is Telegram-only
  return Boolean(params.room || params.game);
}


/** Close Mini App or fall back to history / profile. */
export function goBack() {
  try {
    const wa = getTelegramWebApp();
    if (wa?.close) {
      wa.close();
      return;
    }
  } catch {
    // ignore
  }
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  window.location.href = "/webapp/?page=profile";
}
