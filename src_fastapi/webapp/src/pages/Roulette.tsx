import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError } from "../api/client";
import type { RoomState } from "../types";
import { getUrlParams, getCurrentUserId, haptic, hapticNotify, goBack } from "../lib/telegram";
import { soundWin, soundLose, soundSpin, soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import Confetti from "../components/Confetti";
import { BackIcon, CoinIcon } from "../components/icons";

const RED_NUMBERS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

function numberColor(n: number): string {
  if (n === 0) return "green";
  return RED_NUMBERS.has(n) ? "red" : "black";
}

const SECTORS = 37; // 0..36

// Pre-compute the wheel sector colors
const WHEEL_COLORS = Array.from({ length: SECTORS }, (_, i) => numberColor(i));

interface BetEntry {
  type: "color" | "number" | "parity";
  value: string | number;
  amount: number;
}

export default function Roulette() {
  const params = getUrlParams();
  const chatId = params.chat_id ? parseInt(params.chat_id) : null;
  const myId = getCurrentUserId();
  const [room, setRoom] = useState<RoomState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(true);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState<{ number: number; color: string } | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [betAmount, setBetAmount] = useState("10");
  const [betType, setBetType] = useState<"color" | "number" | "parity">("color");
  const [betValue, setBetValue] = useState<string>("red");
  const [numValue, setNumValue] = useState("0");
  const [payout, setPayout] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.createRoom({ game_type: "roulette", chat_id: chatId ?? myId ?? undefined, bet: 0 })
      .then((r) => { setRoom(r as RoomState); setCreating(false); })
      .catch((e) => {
        setError(e instanceof ApiError ? (e.detail?.toString?.() ?? e.message) : e instanceof Error ? e.message : String(e));
        setCreating(false);
      });
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleSpin = async () => {
    if (!room || spinning) return;
    const amount = parseInt(betAmount) || 0;
    if (amount <= 0) { hapticNotify("error"); setError("Введите ставку"); return; }

    // Join first if needed
    if (room.status === "waiting") {
      try {
        const joined = await api.joinRoom(room.id, { bet: amount });
        setRoom(joined);
      } catch (e) {
        const msg = e instanceof ApiError ? (e.detail?.toString?.() ?? e.message) : e instanceof Error ? e.message : String(e);
        setError(msg);
        hapticNotify("error");
        return;
      }
    }

    setSpinning(true);
    soundSpin();
    haptic("medium");

    const betValueFinal = betType === "number" ? parseInt(numValue) : betValue;
    const bets: BetEntry[] = [{ type: betType, value: betValueFinal, amount }];

    try {
      const res = await api.roomAction(room.id, { bets }) as { number: number; color: string; results: Array<{ user_id: number; bet: number; won: number; won_net: number }> };
      setResult({ number: res.number, color: res.color });
      const myResult = res.results.find((r) => r.user_id === myId);
      const won = myResult?.won_net ?? 0;
      setPayout(won);
      if (won > 0) {
        hapticNotify("success");
        soundWin();
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 4000);
      } else {
        hapticNotify("warning");
        soundLose();
      }
    } catch (e) {
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

  // Compute spin angle: the winning number should land at the pointer (top)
  const spinAngle = result ? 360 * 5 + (360 / SECTORS) * (SECTORS - result.number) : 0;
  const resultColor = result ? result.color : "white";

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6 gap-4">
      {showConfetti && <Confetti count={80} duration={4} />}

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-black gradient-text">РУЛЕТКА</h1>
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

      {/* Wheel */}
      <GlassCard glow className="w-full max-w-sm flex flex-col items-center py-6">
        <div className="relative w-56 h-56 max-w-full">
          {/* Pointer */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-2 z-10 text-white">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="12 2 2 22 22 22" />
            </svg>
          </div>
          {/* Wheel SVG */}
          <motion.svg
            viewBox="0 0 200 200"
            className="w-full h-full"
            animate={spinning ? { rotate: spinAngle } : {}}
            transition={spinning ? { duration: 4, ease: "easeOut" } : {}}
            style={{ filter: "drop-shadow(0 0 10px rgba(168,85,247,0.4))" }}
          >
            {Array.from({ length: SECTORS }).map((_, i) => {
              const angle = (360 / SECTORS) * i;
              const x1 = 100 + 95 * Math.cos((angle - 90) * Math.PI / 180);
              const y1 = 100 + 95 * Math.sin((angle - 90) * Math.PI / 180);
              const x2 = 100 + 95 * Math.cos((angle + 360 / SECTORS - 90) * Math.PI / 180);
              const y2 = 100 + 95 * Math.sin((angle + 360 / SECTORS - 90) * Math.PI / 180);
              const fill = WHEEL_COLORS[i] === "red" ? "#dc2626" : WHEEL_COLORS[i] === "black" ? "#1a1a2e" : "#22c55e";
              const midAngle = angle + 360 / SECTORS / 2 - 90;
              const tx = 100 + 65 * Math.cos(midAngle * Math.PI / 180);
              const ty = 100 + 65 * Math.sin(midAngle * Math.PI / 180);
              return (
                <g key={i}>
                  <path d={`M100 100 L ${x1} ${y1} A 95 95 0 0 1 ${x2} ${y2} Z`} fill={fill} stroke="#333" strokeWidth="0.5" />
                  <text x={tx} y={ty} textAnchor="middle" dominantBaseline="central" fontSize="8" fill="white" fontWeight="bold">
                    {i}
                  </text>
                </g>
              );
            })}
            <circle cx="100" cy="100" r="15" fill="#0f0f1e" stroke="#a855f7" strokeWidth="2" />
          </motion.svg>
        </div>

        {/* Result */}
        <div className="h-14 flex items-center justify-center">
          <AnimatePresence mode="wait">
            {result && !spinning && (
              <motion.div
                key={result.number}
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                className="flex items-center gap-3"
              >
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-black text-white"
                  style={{ background: resultColor === "red" ? "#dc2626" : resultColor === "black" ? "#1a1a2e" : "#22c55e", border: "2px solid rgba(255,255,255,0.2)" }}
                >
                  {result.number}
                </div>
                {payout !== null && (
                  <span className={`text-lg font-bold ${payout > 0 ? "text-neon-green" : "text-red-400"}`}>
                    {payout > 0 ? `+${payout}` : payout} 🪙
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </GlassCard>

      {/* Bet controls */}
      <GlassCard className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-3">
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

        {/* Bet type selector */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          {(["color", "number", "parity"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setBetType(t); haptic("light"); soundClick(); }}
              className={`py-2 rounded-lg text-sm font-semibold transition-all ${betType === t ? "bg-gradient-to-r from-neon-purple to-purple-700 text-white" : "glass text-white/60"}`}
            >
              {t === "color" ? "Цвет" : t === "number" ? "Число" : "Чёт/нечет"}
            </button>
          ))}
        </div>

        {/* Value selector */}
        {betType === "color" && (
          <div className="grid grid-cols-3 gap-2 mb-4">
            {["red", "black", "green"].map((c) => (
              <button
                key={c}
                onClick={() => { setBetValue(c); haptic("light"); soundClick(); }}
                className={`py-3 rounded-lg font-bold text-white transition-all ${betValue === c ? "ring-2 ring-white" : ""}`}
                style={{ background: c === "red" ? "#dc2626" : c === "black" ? "#1a1a2e" : "#22c55e" }}
              >
                {c === "red" ? "Красн" : c === "black" ? "Чёрн" : "Зел"}
              </button>
            ))}
          </div>
        )}
        {betType === "parity" && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            {["even", "odd"].map((p) => (
              <button
                key={p}
                onClick={() => { setBetValue(p); haptic("light"); soundClick(); }}
                className={`py-3 rounded-lg font-bold transition-all ${betValue === p ? "bg-gradient-to-r from-neon-purple to-purple-700 text-white" : "glass text-white/60"}`}
              >
                {p === "even" ? "Чётное" : "Нечётное"}
              </button>
            ))}
          </div>
        )}
        {betType === "number" && (
          <div className="mb-4">
            <input
              type="number"
              value={numValue}
              onChange={(e) => { setNumValue(e.target.value); haptic("light"); }}
              min="0"
              max="36"
              className="w-full glass rounded-lg px-4 py-3 text-lg font-bold outline-none focus:ring-2 focus:ring-neon-purple"
            />
            <p className="text-white/40 text-xs mt-1">0-36, выплата x36</p>
          </div>
        )}

        <NeonButton
          variant="pink"
          size="lg"
          className="w-full"
          disabled={spinning}
          onClick={handleSpin}
        >
          {spinning ? "Крутится..." : "КРУТИТЬ"}
        </NeonButton>
      </GlassCard>

      <NeonButton variant="cyan" size="sm" onClick={() => goBack()}>
        <span className="flex items-center gap-2"><BackIcon size={16} /> Назад</span>
      </NeonButton>
    </div>
  );
}
