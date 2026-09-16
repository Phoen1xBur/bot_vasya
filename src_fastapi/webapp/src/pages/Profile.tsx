import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, ApiError, formatApiDetail } from "../api/client";
import type { UserProfile, SubscriptionInfo } from "../types";
import { getUrlParams, getCurrentUserId, goBackOrClose, hasTelegramInitData } from "../lib/telegram";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import { CoinIcon, UserIcon, CrownIcon, BackIcon } from "../components/icons";

const TIER_GRADIENTS: Record<string, string> = {
  VIP: "from-amber-400 to-yellow-600",
  PREMIUM: "from-neon-purple to-purple-700",
  ELITE: "from-neon-cyan to-blue-700",
  FREE: "from-gray-500 to-gray-700",
};

export default function Profile() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [canTag, setCanTag] = useState<boolean | null>(null);
  const [tagBusy, setTagBusy] = useState(false);
  const chatIdParam = getUrlParams().chat_id ? parseInt(getUrlParams().chat_id!, 10) : null;

  useEffect(() => {
    const params = getUrlParams();
    const chatId = params.chat_id ? parseInt(params.chat_id) : null;

    Promise.all([
      api.getProfile(chatId),
      api.getMySubscription(),
      chatId ? api.getUserSettings(chatId).catch(() => null) : Promise.resolve(null),
    ])
      .then(([p, s, settings]) => {
        setProfile(p);
        setSub(s);
        if (settings) setCanTag(settings.can_tag);
      })
      .catch((e) => {
        if (e instanceof ApiError) setError(formatApiDetail(e.detail) || e.message);
        else setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
  }, []);

  const onToggleTag = async () => {
    if (!chatIdParam || tagBusy) return;
    setTagBusy(true);
    try {
      const r = await api.toggleTag(chatIdParam);
      setCanTag(r.can_tag);
    } catch (e) {
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setTagBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4 gap-4">
        <GlassCard className="max-w-md text-center">
          <p className="text-red-400">{error}</p>
          <p className="text-white/40 text-sm mt-2">
            {hasTelegramInitData()
              ? "Не удалось загрузить профиль. Закройте WebApp и откройте снова из меню бота."
              : "Откройте WebApp из Telegram (меню бота или кнопка в чате)"}
          </p>
        </GlassCard>
        <NeonButton variant="cyan" onClick={() => goBackOrClose()}>
          <span className="flex items-center gap-2"><BackIcon size={16} /> Назад</span>
        </NeonButton>
      </div>
    );
  }

  const tier = sub?.tier ?? "FREE";
  const tag = sub?.tag ?? "";
  const gradient = TIER_GRADIENTS[tier] ?? TIER_GRADIENTS.FREE;
  const myId = getCurrentUserId();
  const photoUrl = window.Telegram?.WebApp?.initDataUnsafe?.user?.photo_url;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4 gap-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm"
      >
        <GlassCard glow className="text-center">
          <div className="flex justify-center mb-4">
            {photoUrl ? (
              <img
                src={photoUrl}
                alt="avatar"
                className="w-24 h-24 rounded-full border-2 border-neon-purple shadow-lg"
              />
            ) : (
              <div className={`w-24 h-24 rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center`}>
                <UserIcon size={48} className="text-white" />
              </div>
            )}
          </div>
          <h2 className="text-2xl font-bold">{profile?.full_name ?? "Игрок"}</h2>
          {profile?.username && (
            <p className="text-white/50 text-sm">@{profile.username}</p>
          )}
          <p className="text-white/30 text-xs mt-1">ID: {profile?.user_id ?? myId}</p>

          {tag && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: "spring" }}
              className={`inline-flex items-center gap-1 mt-4 px-4 py-1.5 rounded-full bg-gradient-to-r ${gradient} text-white font-bold text-sm`}
            >
              <CrownIcon size={14} />
              {tag}
            </motion.div>
          )}
        </GlassCard>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="w-full max-w-sm"
      >
        <GlassCard className="text-center">
          <div className="flex items-center justify-center gap-2 text-white/60 text-sm uppercase tracking-wide mb-2">
            <CoinIcon size={18} />
            Баланс
          </div>
          <motion.p
            className="text-4xl font-black gradient-text"
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            {profile?.money ?? 0}
          </motion.p>
          <p className="text-white/50 mt-1">{profile?.vasya_coin ?? "васякоинов"}</p>
        </GlassCard>
      </motion.div>

      {sub && sub.status !== "none" && sub.expires_at && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="w-full max-w-sm"
        >
          <GlassCard className="text-center text-sm">
            <p className="text-white/60">
              Подписка активна до:{" "}
              <span className="text-neon-cyan">
                {new Date(sub.expires_at).toLocaleDateString("ru-RU")}
              </span>
            </p>
            {sub.auto_renew && (
              <p className="text-white/40 text-xs mt-1">Автопродление включено</p>
            )}
          </GlassCard>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="w-full max-w-sm flex flex-col gap-2"
      >
        {chatIdParam != null && canTag != null && (
          <GlassCard className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-sm">Тег в чате</p>
              <p className="text-white/40 text-xs">Упоминание ссылкой в сообщениях бота</p>
            </div>
            <NeonButton size="sm" variant={canTag ? "pink" : "green"} disabled={tagBusy} onClick={onToggleTag}>
              {tagBusy ? "…" : canTag ? "Выключить" : "Включить"}
            </NeonButton>
          </GlassCard>
        )}
        <NeonButton className="w-full" variant="purple" onClick={() => (window.location.href = "/webapp/?page=mychats")}>
          Мои чаты
        </NeonButton>
        <NeonButton className="w-full" variant="cyan" onClick={() => (window.location.href = "/webapp/?page=subscribe")}>
          Подписка / донат
        </NeonButton>
      </motion.div>
    </div>
  );
}
