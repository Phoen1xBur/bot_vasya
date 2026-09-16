import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, ApiError, formatApiDetail } from "../api/client";
import type { SubscriptionInfo } from "../types";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import { BackIcon, CrownIcon } from "../components/icons";
import { getUrlParams, goBackOrClose, haptic, hapticNotify } from "../lib/telegram";

interface Plan {
  tier: string;
  tag: string;
  price_kopecks: number;
  work_bonus: number;
  ai_daily_limit: number;
}

const DONATE_PRESETS = [50, 100, 300, 500, 1000];

export default function Subscribe() {
  const params = getUrlParams();
  const initialTab = params.request_func === "donate" || (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("tab") === "donate")
    ? "donate"
    : "sub";
  const [tab, setTab] = useState<"sub" | "donate">(initialTab);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customDonate, setCustomDonate] = useState("100");
  const [renewBusy, setRenewBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<{ plans: Plan[] }>("/api/subscriptions/plans"),
      api.getMySubscription(),
    ])
      .then(([p, s]) => {
        setPlans(p.plans);
        setSub(s);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e))
      )
      .finally(() => setLoading(false));
  }, []);

  const pay = async (body: Record<string, unknown>, key: string) => {
    setBusy(key);
    setError(null);
    try {
      const res = await api.post<{ payment_url: string; order_id: string; amount: number }>(
        "/api/payments/init",
        body
      );
      hapticNotify("success");
      if (res.payment_url) {
        window.location.href = res.payment_url;
      }
    } catch (e) {
      hapticNotify("error");
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setBusy(null);
    }
  };


  const onCancelAutoRenew = async () => {
    if (renewBusy) return;
    setRenewBusy(true);
    setError(null);
    try {
      const r = await api.cancelAutoRenew();
      if (r.subscription) setSub(r.subscription);
    } catch (e) {
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setRenewBusy(false);
    }
  };

  const onResumeAutoRenew = async () => {
    if (renewBusy) return;
    setRenewBusy(true);
    setError(null);
    try {
      const r = await api.resumeAutoRenew();
      if (r.subscription) setSub(r.subscription);
    } catch (e) {
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setRenewBusy(false);
    }
  };

  if (loading)  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 pt-6 max-w-md mx-auto flex flex-col gap-4">
      <h1 className="text-2xl font-black gradient-text text-center flex items-center justify-center gap-2">
        <CrownIcon size={24} /> Подписка и донат
      </h1>

      <div className="flex gap-1">
        {(
          [
            ["sub", "Подписка"],
            ["donate", "Донат"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setTab(id);
              haptic("light");
            }}
            className={`flex-1 py-2.5 rounded-xl text-sm font-semibold ${
              tab === id
                ? "bg-gradient-to-r from-neon-purple to-purple-700 text-white"
                : "glass text-white/50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {sub && sub.status !== "none" && (
        <GlassCard className="text-sm text-center flex flex-col gap-2">
          <p>
            Сейчас: <span className="text-neon-cyan font-bold">{sub.tag || sub.tier}</span>
            {sub.expires_at && (
              <> до {new Date(sub.expires_at).toLocaleDateString("ru-RU")}</>
            )}
          </p>
          <p className="text-white/40 text-xs">
            {sub.auto_renew
              ? "Автопродление включено (ежемесячное списание)"
              : sub.has_recurring_key
                ? "Автопродление выключено"
                : "После оплаты карта сохранится для автопродления"}
          </p>
          {sub.auto_renew ? (
            <NeonButton size="sm" variant="pink" disabled={renewBusy} onClick={onCancelAutoRenew}>
              {renewBusy ? "…" : "Отключить автопродление"}
            </NeonButton>
          ) : (
            <NeonButton size="sm" variant="green" disabled={renewBusy} onClick={onResumeAutoRenew}>
              {renewBusy ? "…" : "Включить автопродление"}
            </NeonButton>
          )}
        </GlassCard>
      )}

      {error && <GlassCard className="text-red-400 text-sm">{error}</GlassCard>}

      {tab === "sub" && (
        <div className="flex flex-col gap-3">
          {plans.map((p, i) => (
            <motion.div key={p.tier} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <GlassCard glow={p.tier === "elite"}>
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-bold text-lg">{p.tag || p.tier.toUpperCase()}</p>
                    <p className="text-white/40 text-xs mt-1">
                      бонус к работе +{Math.round(p.work_bonus * 100)}% · AI{" "}
                      {p.ai_daily_limit < 0 ? "∞" : p.ai_daily_limit}/день
                    </p>
                  </div>
                  <p className="text-neon-cyan font-black">{(p.price_kopecks / 100).toFixed(0)}₽</p>
                </div>
                <NeonButton
                  className="w-full mt-3"
                  size="sm"
                  disabled={!!busy}
                  onClick={() =>
                    pay({ payment_type: "subscription", tier: p.tier }, p.tier)
                  }
                >
                  {busy === p.tier ? "Создаю платёж…" : "Оплатить в Mini App"}
                </NeonButton>
              </GlassCard>
            </motion.div>
          ))}
          <p className="text-white/40 text-xs text-center">
            Оплата привязывает карту: дальше списание раз в 30 дней, пока не отключите автопродление.
          </p>
        </div>
      )}

      {tab === "donate" && (
        <GlassCard className="flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-2">
            {DONATE_PRESETS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() =>
                  pay({ payment_type: "donation", amount: r * 100 }, `d${r}`)
                }
                className="glass rounded-xl py-3 font-bold hover:border-neon-purple/50"
                disabled={!!busy}
              >
                {r}₽
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="number"
              min={50}
              value={customDonate}
              onChange={(e) => setCustomDonate(e.target.value)}
              className="flex-1 glass rounded-lg px-3 py-2 outline-none"
              placeholder="Своя сумма ₽"
            />
            <NeonButton
              size="sm"
              disabled={!!busy}
              onClick={() => {
                const r = parseInt(customDonate, 10);
                if (!r || r < 50) {
                  setError("Минимум 50₽");
                  return;
                }
                pay({ payment_type: "donation", amount: r * 100 }, "custom");
              }}
            >
              Оплатить
            </NeonButton>
          </div>
        </GlassCard>
      )}

      <div className="flex justify-center">
        <NeonButton variant="cyan" size="sm" onClick={() => goBackOrClose("/webapp/?page=profile")}>
          <span className="flex items-center gap-2">
            <BackIcon size={16} /> Назад
          </span>
        </NeonButton>
      </div>
    </div>
  );
}
