import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError } from "../api/client";
import type { RoomState } from "../types";
import { getUrlParams, haptic, hapticNotify, goBack } from "../lib/telegram";
import { soundWin, soundLose, soundSpin, soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import Confetti from "../components/Confetti";
import { BackIcon, CoinIcon } from "../components/icons";

const SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"];
const PAYOUTS: Record<string, number> = {
  "💎": 10,
  "7️⃣": 25,
  "⭐": 5,
  "🔔": 4,
  "🍋": 3,
  "🍒": 2,
};

export default function Slots() {
  const params = getUrlParams();
  const chatId = params.chat_id ? parseInt(params.chat_id) : null;
  const myId = getCurrentUserId();
  const [room, setRoom] = useState<RoomState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(true);
  const [spinning, setSpinning] = useState(false);
  const [reels, setReels] = useState<string[]>(["🍒", "🍋", "🔔"]);
  const [result, setResult] = useState<{ won: number; bet: number; net: number } | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [betAmount, setBetAmount] = useState("10");
  const spinRef = useRef(false);

  useEffect(() => {
    api.createRoom({ game_type: "slots", chat_id: chatId ?? myId ?? undefined, bet: 0 })
      .then((r) => { setRoom(r as RoomState); setCreating(false); })
      .catch((e) => {
        setError(e instanceof ApiError ? (e.detail?.toString?.() ?? e.message) : e instanceof Error ? e.message : String(e));
        setCreating(false);
      });
  }, []);

  const handleSpin = async () => {
    if (!room || spinning) return;
    const bet = parseInt(betAmount) || 0;
    if (bet <= 0) { hapticNotify("error"); setError("Введите ставку"); return; }

    setSpinning(true);
    setResult(null);
    setError(null);
    soundSpin();
    haptic("medium");

    // Animate reels spinning
    let ticks = 0;
    const spinInterval = setInterval(() => {
      setReels([SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)], SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)], SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)]]);
      soundClick();
      ticks++;
    }, 80);

    try {
      const res = await api.roomAction(room.id, { bet }) as { reels: string[]; won: number; bet: number; net: number };
      clearInterval(spinInterval);
      setReels(res.reels);
      setResult({ won: res.won, bet: res.bet, net: res.net });
      if (res.won > 0) {
        hapticNotify("success");
        soundWin();
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 4000);
      } else {
        hapticNotify("warning");
        soundLose();
      }
    } catch (e) {
      clearInterval(spinInterval);
      const msg = e instanceof ApiError ? (e.detail?.toString?.() ?? e.message) : e instanceof Error ? e.message : String(e);
      setError(msg);
      hapticNotify("error");
    } finally {
      setSpinning(false);
    }
  };

  if (creating) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  const isJackpot = reels[0] === reels[1] && reels[1] === reels[2];
  const multiplier = isJackpot ? PAYOUTS[reels[0]] : reels[0] === reels[1] || reels[1] === reels[2] || reels[0] === reels[2] ? "x0.5" : null;

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6 gap-4">
      {showConfetti && <Confetti count={70} duration={4} />}

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-black gradient-text">СЛОТЫ</h1>
        <p className="text-white/50 text-xs mt-1">3 в ряд = джекпот!</p>
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

      {/* Slot machine */}
      <GlassCard glow className="w-full max-w-sm">
        <div className="grid grid-cols-3 gap-2 mb-2">
          {reels.map((symbol, i) => (
            <div
              key={i}
              className="aspect-square glass-dark rounded-xl flex items-center justify-center text-6xl relative overflow-hidden"
            >
              {spinning ? (
                <motion.div
                  animate={{ y: [0, -40, 0] }}
                  transition={{ duration: 0.15, repeat: Infinity }}
                  className="text-6xl"
                >
                  {symbol}
                </motion.div>
              ) : (
                <motion.div
                  key={symbol}
                  initial={{ scale: 0, rotate: -360 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: "spring", stiffness: 200, delay: i * 0.1 }}
                  className={isJackpot ? "animate-pulse-glow" : ""}
                >
                  {symbol}
                </motion.div>
              )}
              {/* Glow line */}
              <div className="absolute inset-y-0 left-0 right-0 border-y-2 border-neon-purple/20" />
            </div>
          ))}
        </div>

        {/* Result */}
        <div className="h-10 flex items-center justify-center">
          <AnimatePresence mode="wait">
            {result && !spinning && (
              <motion.div
                key={result.net}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center"
              >
                {result.won > 0 ? (
                  <span className="text-xl font-black text-neon-green neon-text">
                    +{result.won} 🪙 {multiplier && multiplier !== "x0.5" ? `(${multiplier}x)` : ""}
                  </span>
                ) : (
                  <span className="text-lg font-bold text-red-400">
                    -{result.bet} 🪙
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </GlassCard>

      {/* Bet input */}
      <GlassCard className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-2">
          <CoinIcon size={18} className="text-neon-purple" />
          <span className="text-white/60 text-sm">Ставка</span>
        </div>
        <input
          type="number"
          value={betAmount}
          onChange={(e) => { setBetAmount(e.target.value); haptic("light"); }}
          min="1"
          className="w-full glass rounded-lg px-4 py-3 text-lg font-bold mb-4 outline-none focus:ring-2 focus:ring-neon-purple"
        />
        <NeonButton
          variant="purple"
          size="lg"
          className="w-full"
          disabled={spinning}
          onClick={handleSpin}
        >
          {spinning ? "Крутится..." : "🎰 КРУТИТЬ"}
        </NeonButton>
      </GlassCard>

      {/* Quick bet */}
      <div className="flex gap-2">
        {[5, 10, 50, 100].map((v) => (
          <button
            key={v}
            onClick={() => { setBetAmount(String(v)); haptic("light"); soundClick(); }}
            className="glass rounded-lg px-3 py-1.5 text-sm hover:bg-white/10"
          >
            {v}
          </button>
        ))}
      </div>

      <NeonButton variant="cyan" size="sm" onClick={() => goBack()}>
        <span className="flex items-center gap-2"><BackIcon size={16} /> Назад</span>
      </NeonButton>
    </div>
  );
}
