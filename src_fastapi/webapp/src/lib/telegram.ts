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
  | "mychats"
  | "subscribe"
  | "payment_success"
  | "payment_fail";

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
  let page = (u.get("page") as PageName) || "profile";
  // Legacy return URLs: ?page=payment&status=success|fail
  if ((page as string) === "payment") {
    const st = (u.get("status") || "").toLowerCase();
    page = st === "fail" || st === "error" ? "payment_fail" : "payment_success";
  }
  return {
    page,
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
  const html = document.documentElement;
  const params = new URLSearchParams(window.location.search);
  const page = params.get("page") || "";
  const forceDark =
    page === "payment" ||
    page === "payment_success" ||
    page === "payment_fail" ||
    page === "subscribe" ||
    page === "roulette";
  const scheme = forceDark ? "dark" : (tg?.colorScheme ?? "dark");
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

/** Back: history if possible, else profile page, else close WebApp. */
export function goBackOrClose(fallback: string = "/webapp/?page=profile") {
  try {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
  } catch {
    // ignore
  }
  try {
    window.location.assign(fallback);
    return;
  } catch {
    // ignore
  }
  try {
    getTelegramWebApp()?.close();
  } catch {
    // ignore
  }
}

/** True when running inside Telegram WebApp with initData. */
export function hasTelegramInitData(): boolean {
  return Boolean(getInitData());
}
