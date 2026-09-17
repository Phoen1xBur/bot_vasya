import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError } from "../api/client";
import type { RoomState } from "../types";
import { getUrlParams, getCurrentUserId, haptic, hapticNotify, goBack } from "../lib/telegram";
import { soundWin, soundLose, soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import Confetti from "../components/Confetti";
import { BackIcon, CoinIcon } from "../components/icons";

type BjState = {
  phase: string;
  player: string[];
  dealer: string[];
  player_value: number;
  dealer_value: number;
  bet: number;
  result?: string | null;
  payout?: number;
  message?: string | null;
  net?: number | null;
};

function CardFace({ card }: { card: string }) {
  const hidden = card === "??";
  const red = !hidden && (card.includes("♥") || card.includes("♦"));
  return (
    <motion.div
      initial={{ scale: 0.5, rotateY: 90 }}
      animate={{ scale: 1, rotateY: 0 }}
      className={`w-14 h-20 rounded-xl flex items-center justify-center text-base font-black shadow-lg border border-white/15 ${
        hidden
          ? "bg-gradient-to-br from-indigo-700 to-purple-900 text-white/50"
          : "bg-white"
      } ${red ? "text-red-600" : "text-slate-900"}`}
    >
      {hidden ? "🂠" : card}
    </motion.div>
  );
}

export default function Blackjack() {
  const params = getUrlParams();
  const chatId = params.chat_id ? parseInt(params.chat_id) : null;
  const myId = getCurrentUserId();
  const [room, setRoom] = useState<RoomState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(true);
  const [busy, setBusy] = useState(false);
  const [betAmount, setBetAmount] = useState("10");
  const [balance, setBalance] = useState<number | null>(null);
  const [hand, setHand] = useState<BjState | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);

  const refreshBalance = async () => {
    try {
      const b = await api.getBalance(chatId ?? myId ?? undefined);
      setBalance(b.money);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    void refreshBalance();
    api
      .createRoom({ game_type: "blackjack", chat_id: chatId ?? myId, bet: 0 })
      .then((r) => {
        setRoom(r as RoomState);
        setCreating(false);
      })
      .catch((e) => {
        setError(
          e instanceof ApiError
            ? (e.detail?.toString?.() ?? e.message)
            : e instanceof Error
              ? e.message
              : String(e)
        );
        setCreating(false);
      });
  }, []);

  const run = async (op: "deal" | "hit" | "stand") => {
    if (!room || busy) return;
    if (op === "deal") {
      const bet = parseInt(betAmount) || 0;
      if (bet <= 0) {
        hapticNotify("error");
        setError("Введите ставку");
        return;
      }
    }
    setBusy(true);
    setError(null);
    haptic("medium");
    soundClick();
    try {
      const action =
        op === "deal" ? { op, bet: parseInt(betAmount) || 0 } : { op };
      const res = (await api.roomAction(room.id, action)) as BjState;
      const net =
        typeof res.net === "number"
          ? res.net
          : res.phase === "finished"
            ? (res.payout ?? 0) - (res.bet ?? 0)
            : null;
      setHand({ ...res, net });
      void refreshBalance();
      if (res.phase === "finished") {
        if (res.result === "win" || res.result === "blackjack") {
          hapticNotify("success");
          soundWin();
          setShowConfetti(true);
          setTimeout(() => setShowConfetti(false), 3500);
        } else if (res.result === "lose") {
          hapticNotify("warning");
          soundLose();
        } else {
          hapticNotify("success");
        }
      }
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? (e.detail?.toString?.() ?? e.message)
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
      hapticNotify("error");
    } finally {
      setBusy(false);
    }
  };

  if (creating) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  const phase = hand?.phase ?? "bet";
  const finished = phase === "finished";
  const playing = phase === "player";

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6 gap-4">
      {showConfetti && <Confetti count={60} duration={3.5} />}

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-black gradient-text">БЛЭКДЖЕК</h1>
        <p className="text-white/50 text-xs mt-1">До 21 против дилера</p>
        <p className="mt-2 text-sm font-semibold text-neon-purple">
          Баланс: {balance === null ? "…" : balance} 🪙
        </p>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass rounded-lg px-4 py-2 text-red-400 text-sm"
        >
          {error}
        </motion.div>
      )}

      <GlassCard glow className="w-full max-w-sm">
        <p className="text-white/50 text-xs mb-2 text-center">
          Дилер{hand ? ` · ${hand.dealer_value}` : ""}
        </p>
        <div className="flex gap-2 justify-center min-h-[5.5rem] mb-4 flex-wrap">
          {(hand?.dealer ?? []).map((c, i) => (
            <CardFace key={`d-${i}-${c}`} card={c} />
          ))}
          {!hand && <span className="text-white/30 text-sm self-center">—</span>}
        </div>

        <div className="h-px bg-white/10 my-2" />

        <p className="text-white/50 text-xs mb-2 text-center">
          Вы{hand ? ` · ${hand.player_value}` : ""}
        </p>
        <div className="flex gap-2 justify-center min-h-[5.5rem] flex-wrap">
          {(hand?.player ?? []).map((c, i) => (
            <CardFace key={`p-${i}-${c}`} card={c} />
          ))}
          {!hand && (
            <span className="text-white/30 text-sm self-center">Сделайте ставку</span>
          )}
        </div>

        <div className="h-12 flex items-center justify-center mt-3">
          <AnimatePresence mode="wait">
            {finished && hand?.message && (
              <motion.div
                key={hand.message}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center"
              >
                <p
                  className={`text-lg font-black ${
                    hand.result === "lose"
                      ? "text-red-400"
                      : hand.result === "push"
                        ? "text-amber-300"
                        : "text-neon-green neon-text"
                  }`}
                >
                  {hand.message}
                </p>
                {typeof hand.net === "number" && (
                  <p className="text-sm text-white/60 mt-1">
                    {hand.net >= 0 ? "+" : ""}
                    {hand.net} 🪙
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </GlassCard>

      <GlassCard className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-2">
          <CoinIcon size={18} className="text-neon-purple" />
          <span className="text-white/60 text-sm">Ставка</span>
        </div>
        <input
          type="number"
          value={betAmount}
          onChange={(e) => {
            setBetAmount(e.target.value);
            haptic("light");
          }}
          min="1"
          disabled={playing || busy}
          className="w-full glass rounded-lg px-4 py-3 text-lg font-bold mb-3 outline-none focus:ring-2 focus:ring-neon-purple disabled:opacity-50"
        />
        <div className="flex gap-2 mb-3">
          {[5, 10, 50, 100].map((v) => (
            <button
              key={v}
              disabled={playing || busy}
              onClick={() => {
                setBetAmount(String(v));
                haptic("light");
                soundClick();
              }}
              className="glass rounded-lg px-3 py-1.5 text-sm hover:bg-white/10 disabled:opacity-40"
            >
              {v}
            </button>
          ))}
        </div>

        {!playing ? (
          <NeonButton
            variant="purple"
            size="lg"
            className="w-full"
            disabled={busy}
            onClick={() => run("deal")}
          >
            {busy ? "…" : finished ? "🃏 ЕЩЁ РАЗ" : "🃏 РАЗДАТЬ"}
          </NeonButton>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <NeonButton
              variant="cyan"
              size="lg"
              disabled={busy}
              onClick={() => run("hit")}
            >
              Взять
            </NeonButton>
            <NeonButton
              variant="purple"
              size="lg"
              disabled={busy}
              onClick={() => run("stand")}
            >
              Хватит
            </NeonButton>
          </div>
        )}
      </GlassCard>

      <NeonButton variant="cyan" size="sm" onClick={() => goBack()}>
        <span className="flex items-center gap-2">
          <BackIcon size={16} /> Назад
        </span>
      </NeonButton>
    </div>
  );
}
