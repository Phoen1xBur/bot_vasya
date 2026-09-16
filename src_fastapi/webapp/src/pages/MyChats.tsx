import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, ApiError, formatApiDetail } from "../api/client";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import { BackIcon } from "../components/icons";
import { goBackOrClose, haptic, hapticNotify } from "../lib/telegram";

interface ChatRow {
  chat_id: number;
  answer_chance: number;
  ai_generate_text: boolean;
  member_status: string;
  can_tag: boolean;
  money: number;
}

export default function MyChats() {
  const [chats, setChats] = useState<ChatRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ChatRow | null>(null);
  const [chance, setChance] = useState("5");
  const [ai, setAi] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ chats: ChatRow[] }>("/api/chats/mine");
      setChats(res.chats);
    } catch (e) {
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const open = (c: ChatRow) => {
    setSelected(c);
    setChance(String(c.answer_chance));
    setAi(!!c.ai_generate_text);
    haptic("light");
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await api.patchChatSettings(selected.chat_id, {
        answer_chance: parseInt(chance, 10),
        ai_generate_text: ai,
      });
      setChats((prev) =>
        prev.map((c) =>
          c.chat_id === selected.chat_id
            ? { ...c, answer_chance: res.answer_chance, ai_generate_text: res.ai_generate_text }
            : c
        )
      );
      setSelected((s) =>
        s
          ? { ...s, answer_chance: res.answer_chance, ai_generate_text: res.ai_generate_text }
          : s
      );
      hapticNotify("success");
    } catch (e) {
      hapticNotify("error");
      setError(e instanceof ApiError ? formatApiDetail(e.detail) || e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const statusRu: Record<string, string> = {
    owner: "владелец",
    administrator: "админ",
    member: "участник",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 pt-6 max-w-lg mx-auto flex flex-col gap-3">
      <h1 className="text-2xl font-black gradient-text text-center">Мои чаты</h1>
      <p className="text-white/50 text-sm text-center">
        Чаты, где вы админ и Вася на месте. Можно менять шанс ответа и ИИ.
      </p>

      {error && <GlassCard className="text-red-400 text-sm">{error}</GlassCard>}

      {!selected ? (
        <>
          {chats.length === 0 && (
            <GlassCard className="text-center text-white/50">
              Нет чатов, где вы администратор (или бот ещё не видел ваше членство).
            </GlassCard>
          )}
          {chats.map((c, i) => (
            <motion.div key={c.chat_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <GlassCard
                className="cursor-pointer hover:border-neon-purple/40"
                onClick={() => open(c)}
              >
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <p className="font-bold text-white">Чат {c.chat_id}</p>
                    <p className="text-white/40 text-xs mt-1">
                      {statusRu[c.member_status] || c.member_status} · шанс {c.answer_chance}% · ИИ{" "}
                      {c.ai_generate_text ? "вкл" : "выкл"}
                    </p>
                  </div>
                  <span className="text-neon-cyan text-sm">Настроить →</span>
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </>
      ) : (
        <GlassCard glow className="flex flex-col gap-4">
          <div>
            <p className="text-white/40 text-xs">Чат</p>
            <p className="font-bold text-lg">{selected.chat_id}</p>
          </div>
          <label className="flex flex-col gap-1">
            <span className="text-white/60 text-sm">Шанс ответа Васи (0–100%)</span>
            <input
              type="number"
              min={0}
              max={100}
              value={chance}
              onChange={(e) => setChance(e.target.value)}
              className="glass rounded-lg px-4 py-3 outline-none focus:ring-2 focus:ring-neon-purple"
            />
          </label>
          <label className="flex items-center justify-between gap-3 glass rounded-lg px-4 py-3">
            <span className="text-white/80 text-sm">ИИ-генерация ответов</span>
            <input
              type="checkbox"
              checked={ai}
              onChange={(e) => setAi(e.target.checked)}
              className="w-5 h-5 accent-purple-500"
            />
          </label>
          <p className="text-white/40 text-xs">
            Личный тег в этом чате: {selected.can_tag ? "включён" : "выключен"} (переключается в
            профиле)
          </p>
          <div className="flex gap-2">
            <NeonButton variant="cyan" size="sm" onClick={() => setSelected(null)}>
              Назад к списку
            </NeonButton>
            <NeonButton size="sm" disabled={saving} onClick={save}>
              {saving ? "Сохраняю…" : "Сохранить"}
            </NeonButton>
          </div>
        </GlassCard>
      )}

      <div className="flex justify-center pt-2">
        <NeonButton variant="cyan" size="sm" onClick={() => goBackOrClose("/webapp/?page=profile")}>
          <span className="flex items-center gap-2">
            <BackIcon size={16} /> В профиль
          </span>
        </NeonButton>
      </div>
    </div>
  );
}
