import { useEffect } from "react";
import { motion } from "framer-motion";
import { hapticNotify, getTelegramWebApp } from "../lib/telegram";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";

type Kind = "success" | "fail";

function forceDarkTheme() {
  const html = document.documentElement;
  html.classList.remove("light");
  html.classList.add("dark");
  html.style.colorScheme = "dark";
  document.body.style.background = "#0f0f1e";
  document.body.style.color = "#ffffff";
  try {
    const tg = getTelegramWebApp();
    tg?.setHeaderColor?.("#0f0f1e");
    tg?.setBackgroundColor?.("#0f0f1e");
  } catch {
    /* ignore */
  }
}

export default function PaymentResult({ kind }: { kind: Kind }) {
  const ok = kind === "success";

  useEffect(() => {
    forceDarkTheme();
    hapticNotify(ok ? "success" : "error");
  }, [ok]);

  const openBot = () => {
    const username = (import.meta as { env?: { VITE_BOT_USERNAME?: string } }).env?.VITE_BOT_USERNAME
      || "vasya_fun_bot";
    const u = username.replace(/^@/, "");
    window.open(`https://t.me/${u}`, "_blank");
  };

  const close = () => {
    try {
      getTelegramWebApp()?.close();
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="bg-mesh flex flex-col items-center justify-center min-h-screen p-4 text-white">
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        <GlassCard className="text-center p-8 neon-glow glass-dark">
          <div
            className={`mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full text-3xl ${
              ok
                ? "bg-gradient-to-br from-emerald-400 to-cyan-500"
                : "bg-gradient-to-br from-rose-500 to-orange-600"
            }`}
          >
            {ok ? "✓" : "!"}
          </div>
          <h1 className="text-2xl font-black gradient-text">
            {ok ? "Оплата прошла успешно" : "Оплата не завершена"}
          </h1>
          <p className="mt-3 text-sm text-white/70 leading-relaxed">
            {ok
              ? "VIP / Premium / Elite активируется автоматически после подтверждения платежа. Управлять подпиской можно в профиле Mini App."
              : "Платёж отменён или произошла ошибка. Попробуйте ещё раз из профиля Mini App или через бота."}
          </p>
          <div className="mt-6 flex flex-col gap-3">
            {ok ? (
              <>
                <NeonButton onClick={openBot}>Открыть бота</NeonButton>
                <a
                  href="/webapp/?page=profile"
                  className="text-sm text-cyan-300/90 underline-offset-2 hover:underline"
                >
                  Перейти в профиль Mini App
                </a>
                <button
                  type="button"
                  onClick={close}
                  className="text-xs text-white/40 hover:text-white/70"
                >
                  Закрыть окно
                </button>
              </>
            ) : (
              <>
                <NeonButton onClick={() => (window.location.href = "/webapp/?page=subscribe")}>
                  Попробовать снова
                </NeonButton>
                <NeonButton variant="cyan" onClick={close}>
                  Закрыть
                </NeonButton>
              </>
            )}
          </div>
        </GlassCard>
      </motion.div>
    </div>
  );
}
