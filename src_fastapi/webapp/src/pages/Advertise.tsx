import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError, formatApiDetail } from "../api/client";
import type { AdRules, AdCampaignResponse } from "../types";
import { haptic, hapticNotify, hasTelegramInitData } from "../lib/telegram";
import { soundClick, soundWin } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import { BackIcon, CheckIcon, AdIcon } from "../components/icons";

const FALLBACK_PRICE_PER_1000 = 1000_00; // kopecks; overwritten by /api/ads/rules

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    ai_pending: "На проверке AI",
    ai_approved: "Одобрено AI — можно оплатить",
    ai_rejected: "Отклонено AI",
    admin_pending: "На ручной модерации",
    approved: "Одобрено админом",
    rejected: "Отклонено",
    paid: "Оплачено",
    sending: "Отправляется",
    sent: "Отправлено",
    cancelled: "Отменено",
    draft: "Черновик",
  };
  return map[status] || status;
}

function canPayStatus(status: string): boolean {
  return status === "ai_approved" || status === "admin_pending";
}

export default function Advertise() {
  const [rules, setRules] = useState<AdRules | null>(null);
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [target, setTarget] = useState("");
  const [contact, setContact] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [paying, setPaying] = useState(false);
  const [result, setResult] = useState<AdCampaignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAdRules()
      .then(setRules)
      .catch((e) => {
        const msg =
          e instanceof ApiError
            ? formatApiDetail(e.detail) || e.message
            : e instanceof Error
              ? e.message
              : "Не удалось загрузить правила";
        setError(msg);
      });
  }, []);

  const targetNum = parseInt(target, 10) || 0;
  const pricePer1000 =
    typeof rules?.price_per_1000 === "number" && rules.price_per_1000 > 0
      ? rules.price_per_1000
      : FALLBACK_PRICE_PER_1000;
  const estimate = targetNum > 0 ? Math.ceil(targetNum / 1000) * pricePer1000 : 0;

  const handleSubmit = async () => {
    if (!hasTelegramInitData()) {
      hapticNotify("error");
      setError("Откройте форму через Telegram Mini App (нет initData для авторизации)");
      return;
    }
    if (!text.trim() || !link.trim() || targetNum <= 0) {
      hapticNotify("error");
      setError("Заполните текст, ссылку и целевую аудиторию");
      return;
    }
    if (!accepted) {
      hapticNotify("error");
      setError("Необходимо согласие с правилами");
      return;
    }
    setSubmitting(true);
    setError(null);
    haptic("medium");
    soundClick();
    try {
      const res = await api.submitCampaign({
        text: text.trim(),
        link: link.trim(),
        target_unique_users: targetNum,
        contact: contact.trim(),
        rules_accepted: accepted,
      });
      setResult(res);
      if (res.status === "ai_rejected") {
        hapticNotify("error");
      } else {
        hapticNotify("success");
        soundWin();
      }
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? formatApiDetail(e.detail) || e.message
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
      hapticNotify("error");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePay = async () => {
    if (!result) return;
    if (!hasTelegramInitData()) {
      hapticNotify("error");
      setError("Откройте форму через Telegram Mini App (нет initData для оплаты)");
      return;
    }
    if (!canPayStatus(result.status)) {
      hapticNotify("error");
      setError("Оплата доступна после одобрения заявки");
      return;
    }
    setPaying(true);
    setError(null);
    haptic("medium");
    soundClick();
    try {
      const pay = await api.initPayment({
        payment_type: "ad_campaign",
        campaign_id: result.campaign_id,
      });
      if (pay.payment_url) {
        window.location.href = pay.payment_url;
        return;
      }
      setError("Не удалось получить ссылку на оплату");
      hapticNotify("error");
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? formatApiDetail(e.detail) || e.message
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
      hapticNotify("error");
    } finally {
      setPaying(false);
    }
  };

  const rejected = result?.status === "ai_rejected" || result?.status === "rejected";
  const aiReason =
    result?.ai_verdict && typeof result.ai_verdict.reason === "string"
      ? result.ai_verdict.reason
      : null;

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6 gap-4">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-black gradient-text flex items-center justify-center gap-2">
          <AdIcon size={28} /> РЕКЛАМА
        </h1>
        <p className="text-white/50 text-xs mt-1">Размещение рекламы в чатах бота</p>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass rounded-lg px-4 py-2 text-red-400 text-sm w-full max-w-md text-center"
        >
          {error}
        </motion.div>
      )}

      <AnimatePresence mode="wait">
        {result ? (
          <motion.div
            key="result"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md"
          >
            <GlassCard glow className="text-center py-8">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200 }}
                className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-4 ${
                  rejected
                    ? "bg-gradient-to-br from-red-500 to-rose-700"
                    : "bg-gradient-to-br from-neon-green to-emerald-600"
                }`}
              >
                <CheckIcon size={32} className="text-white" />
              </motion.div>
              <h2 className="text-xl font-bold">
                {rejected ? "Заявка отклонена" : "Заявка подана!"}
              </h2>
              <p className="text-white/50 text-sm mt-1">{statusLabel(result.status)}</p>
              <p className="text-white/40 text-xs mt-2">
                Цена: {(result.price / 100).toLocaleString("ru-RU")} ₽
              </p>
              {aiReason && (
                <div className="mt-4 glass rounded-lg p-3 text-left text-sm">
                  <p className="text-white/60 mb-1">Комментарий модерации:</p>
                  <p className="text-white/80 text-xs whitespace-pre-wrap">{aiReason}</p>
                </div>
              )}
              {result.ai_verdict && !aiReason && (
                <div className="mt-4 glass rounded-lg p-3 text-left text-sm">
                  <p className="text-white/60 mb-1">AI-вердикт:</p>
                  <pre className="text-white/80 whitespace-pre-wrap text-xs">
                    {JSON.stringify(result.ai_verdict, null, 2)}
                  </pre>
                </div>
              )}
              <div className="mt-6 flex flex-col gap-3 items-center">
                {canPayStatus(result.status) && (
                  <NeonButton
                    variant="green"
                    size="lg"
                    className="w-full"
                    disabled={paying}
                    onClick={handlePay}
                  >
                    {paying
                      ? "Открываем оплату..."
                      : `ОПЛАТИТЬ ${(result.price / 100).toLocaleString("ru-RU")} ₽`}
                  </NeonButton>
                )}
                <NeonButton
                  variant="cyan"
                  onClick={() => {
                    setResult(null);
                    setText("");
                    setLink("");
                    setTarget("");
                    setContact("");
                    setAccepted(false);
                    setError(null);
                  }}
                >
                  Новая заявка
                </NeonButton>
              </div>
            </GlassCard>
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="w-full max-w-md flex flex-col gap-4"
          >
            {rules && (
              <GlassCard>
                <h3 className="font-bold text-sm mb-2 text-neon-cyan">Правила</h3>
                <ul className="space-y-1">
                  {rules.rules.map((r, i) => (
                    <li key={i} className="text-white/60 text-xs flex gap-2">
                      <span className="text-neon-purple">•</span> {r}
                    </li>
                  ))}
                </ul>
                <p className="text-white/40 text-xs mt-2">
                  Доступно уникальных пользователей:{" "}
                  <span className="text-neon-green font-bold">{rules.total_unique_users}</span>
                </p>
                <p className="text-white/40 text-xs mt-1">
                  Тариф:{" "}
                  <span className="text-neon-cyan font-bold">
                    {(pricePer1000 / 100).toLocaleString("ru-RU")} ₽
                  </span>{" "}
                  за 1000 чел.
                </p>
              </GlassCard>
            )}

            <GlassCard className="flex flex-col gap-3">
              <div>
                <label className="text-white/60 text-sm block mb-1">Текст рекламы</label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={4}
                  className="w-full glass rounded-lg px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-neon-purple resize-none"
                  placeholder="Введите текст рекламного сообщения..."
                />
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Ссылка</label>
                <input
                  type="url"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                  className="w-full glass rounded-lg px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-neon-purple"
                  placeholder="https://..."
                />
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Целевая аудитория (чел.)</label>
                <input
                  type="number"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  min="1"
                  className="w-full glass rounded-lg px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-neon-purple"
                  placeholder="1000"
                />
                {rules && targetNum > rules.total_unique_users && (
                  <p className="text-amber-400 text-xs mt-1">
                    Внимание: запрошено больше, чем доступно ({rules.total_unique_users})
                  </p>
                )}
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Контакт</label>
                <input
                  type="text"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  className="w-full glass rounded-lg px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-neon-purple"
                  placeholder="@username или email"
                />
              </div>

              {estimate > 0 && (
                <div className="glass rounded-lg px-4 py-2 text-sm flex justify-between items-center">
                  <span className="text-white/60">Примерная цена:</span>
                  <span className="text-neon-green font-bold">
                    {(estimate / 100).toLocaleString("ru-RU")} ₽
                  </span>
                </div>
              )}

              <label className="flex items-start gap-3 cursor-pointer">
                <button
                  type="button"
                  onClick={() => {
                    setAccepted(!accepted);
                    haptic("light");
                  }}
                  className={`mt-0.5 w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 transition-all ${
                    accepted
                      ? "bg-gradient-to-br from-neon-green to-emerald-600"
                      : "glass border border-white/20"
                  }`}
                >
                  {accepted && <CheckIcon size={14} className="text-white" />}
                </button>
                <span className="text-white/60 text-xs">
                  Я согласен с правилами размещения рекламы и подтверждаю, что реклама не нарушает
                  законов РФ
                </span>
              </label>

              <NeonButton
                variant="purple"
                size="lg"
                className="w-full mt-2"
                disabled={submitting}
                onClick={handleSubmit}
              >
                {submitting ? "Отправка..." : "ПОДАТЬ ЗАЯВКУ"}
              </NeonButton>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      <NeonButton variant="cyan" size="sm" onClick={() => window.history.back()}>
        <span className="flex items-center gap-2">
          <BackIcon size={16} /> Назад
        </span>
      </NeonButton>
    </div>
  );
}
