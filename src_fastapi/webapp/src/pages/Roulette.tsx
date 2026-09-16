import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError, formatApiDetail } from "../api/client";
import type { RoomState } from "../types";
import {
  getUrlParams,
  getCurrentUserId,
  haptic,
  hapticNotify,
  goBackOrClose,
} from "../lib/telegram";
import { soundWin, soundLose, soundSpin, soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import Confetti from "../components/Confetti";
import { BackIcon, CoinIcon } from "../components/icons";

const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
const SECTORS = 37;
/** European wheel order (clockwise from 0 under pointer baseline). */
const WHEEL_ORDER = [
  0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
  5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
];

function numberColor(n: number): "red" | "black" | "green" {
  if (n === 0) return "green";
  return RED.has(n) ? "red" : "black";
}

type BetType = "number" | "color" | "parity" | "highlow" | "dozen" | "column";
interface ChipBet {
  type: BetType;
  value: string | number;
  amount: number;
  key: string;
}

const CHIP_AMOUNTS = [1, 5, 10, 25, 50, 100];

/** Board layout: 3 columns × 12 rows (European). */
const BOARD_ROWS: number[][] = Array.from({ length: 12 }, (_, row) => [
  row * 3 + 1,
  row * 3 + 2,
  row * 3 + 3,
]);

function betKey(type: BetType, value: string | number) {
  return `${type}:${value}`;
}

export default function Roulette() {
  const params = getUrlParams();
  const chatId = params.chat_id ? parseInt(params.chat_id, 10) : null;
  const roomFromUrl = params.room;
  const myId = getCurrentUserId();

  const [room, setRoom] = useState<RoomState | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [roomFull, setRoomFull] = useState(false);
  const [spinning, setSpinning] = useState(false);
  const [wheelRot, setWheelRot] = useState(0);
  const [result, setResult] = useState<{ number: number; color: string } | null>(null);
  const [payout, setPayout] = useState<number | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [chip, setChip] = useState(10);
  const [pending, setPending] = useState<ChipBet[]>([]);
  const wheelRotRef = useRef(0);

  const pendingTotal = useMemo(
    () => pending.reduce((s, b) => s + b.amount, 0),
    [pending]
  );

  const refreshBalance = useCallback(async (cid: number | null) => {
    if (!cid) return;
    try {
      const b = await api.get<{ money: number }>("/api/user/balance", { chat_id: cid });
      setBalance(b.money);
    } catch {
      /* ignore */
    }
  }, []);

  const openRoom = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRoomFull(false);
    setInfo(null);
    try {
      let r: RoomState;
      if (roomFromUrl) {
        try {
          r = await api.getRoom(roomFromUrl);
        } catch (e) {
          const msg =
            e instanceof ApiError
              ? formatApiDetail(e.detail) || e.message
              : e instanceof Error
                ? e.message
                : String(e);
          if (/максимум|полн|full/i.test(msg)) {
            setRoomFull(true);
            setError("Комната заполнена");
            setLoading(false);
            return;
          }
          // room missing → create new
          if (!chatId) throw e;
          r = await api.createRoom({ game_type: "roulette", chat_id: chatId, bet: 0 });
        }
      } else {
        if (!chatId) {
          throw new Error("Откройте рулетку из группового чата (кнопка мини-игр)");
        }
        r = await api.createRoom({ game_type: "roulette", chat_id: chatId, bet: 0 });
      }

      // join without charging (bet 0) so мы за столом
      try {
        r = await api.joinRoom(r.id, { bet: 0 });
      } catch (e) {
        const msg =
          e instanceof ApiError
            ? formatApiDetail(e.detail) || e.message
            : e instanceof Error
              ? e.message
              : String(e);
        if (/максимум|полн|full/i.test(msg)) {
          setRoomFull(true);
          setError("Комната заполнена");
          setLoading(false);
          return;
        }
        // already joined / ok
      }

      setRoom(r);
      await refreshBalance(r.chat_id ?? chatId);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? formatApiDetail(e.detail) || e.message
          : e instanceof Error
            ? e.message
            : String(e)
      );
    } finally {
      setLoading(false);
    }
  }, [roomFromUrl, chatId, refreshBalance]);

  useEffect(() => {
    openRoom();
  }, [openRoom]);

  const addBet = (type: BetType, value: string | number) => {
    if (spinning) return;
    haptic("light");
    soundClick();
    const key = betKey(type, value);
    setPending((prev) => {
      const i = prev.findIndex((b) => b.key === key);
      if (i >= 0) {
        const copy = [...prev];
        copy[i] = { ...copy[i], amount: copy[i].amount + chip };
        return copy;
      }
      return [...prev, { type, value, amount: chip, key }];
    });
    setInfo(null);
    setError(null);
  };

  const clearBets = () => {
    if (spinning) return;
    setPending([]);
    haptic("light");
  };

  const amountOn = (type: BetType, value: string | number) => {
    const key = betKey(type, value);
    return pending.find((b) => b.key === key)?.amount ?? 0;
  };

  const createNewGame = async () => {
    if (!chatId) {
      setError("Нет chat_id — откройте из группы");
      return;
    }
    setRoomFull(false);
    setPending([]);
    setResult(null);
    setPayout(null);
    setLoading(true);
    try {
      // cancel old if ours
      if (room?.id && room.initiator_id === myId) {
        try {
          await api.cancelRoom(room.id);
        } catch {
          /* ignore */
        }
      }
      const r = await api.createRoom({ game_type: "roulette", chat_id: chatId, bet: 0 });
      const joined = await api.joinRoom(r.id, { bet: 0 });
      setRoom(joined);
      setInfo(`Новая игра · комната ${joined.id.slice(0, 8)}`);
      await refreshBalance(chatId);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? formatApiDetail(e.detail) || e.message
          : e instanceof Error
            ? e.message
            : String(e)
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSpin = async () => {
    if (!room || spinning) return;
    if (pending.length === 0) {
      hapticNotify("error");
      setError("Поставьте фишки на стол");
      return;
    }
    if (balance != null && pendingTotal > balance) {
      hapticNotify("error");
      setError("Недостаточно васякоинов");
      return;
    }

    setSpinning(true);
    setError(null);
    setInfo(null);
    soundSpin();
    haptic("medium");

    const betsPayload = pending.map((b) => ({
      type: b.type,
      value: b.value,
      amount: b.amount,
      user_id: myId,
    }));

    try {
      const res = (await api.roomAction(room.id, {
        op: "spin",
        bets: betsPayload,
      })) as {
        number: number;
        color: string;
        results: Array<{ user_id: number; bet: number; won: number; won_net: number }>;
        status?: string;
      };

      // Animate wheel to landing number (European order under top pointer)
      const idx = WHEEL_ORDER.indexOf(res.number);
      const sector = 360 / SECTORS;
      const targetMod = ((SECTORS - idx) * sector) % 360;
      const current = wheelRotRef.current;
      const currentMod = ((current % 360) + 360) % 360;
      let delta = targetMod - currentMod;
      if (delta <= 0) delta += 360;
      const next = current + 360 * 6 + delta;
      wheelRotRef.current = next;
      setWheelRot(next);

      // Wait for animation before showing result chrome
      await new Promise((r) => setTimeout(r, 4200));

      setResult({ number: res.number, color: res.color });
      const myResult = res.results.find((r) => r.user_id === myId);
      const wonNet = myResult?.won_net ?? -pendingTotal;
      setPayout(wonNet);
      setPending([]);
      if (wonNet > 0) {
        hapticNotify("success");
        soundWin();
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 3500);
      } else {
        hapticNotify("warning");
        soundLose();
      }
      setRoom((prev) => (prev ? { ...prev, status: res.status || "active" } : prev));
      await refreshBalance(room.chat_id ?? chatId);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? formatApiDetail(e.detail) || e.message
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
      hapticNotify("error");
      if (/полн|максимум|full/i.test(msg)) setRoomFull(true);
    } finally {
      setSpinning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  const ChipBadge = ({ n }: { n: number }) =>
    n > 0 ? (
      <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-amber-400 text-[10px] font-black text-black flex items-center justify-center shadow">
        {n}
      </span>
    ) : null;

  return (
    <div className="flex flex-col min-h-screen p-3 pt-5 gap-3 max-w-6xl mx-auto">
      {showConfetti && <Confetti count={70} duration={3.5} />}

      <div className="text-center">
        <h1 className="text-2xl sm:text-3xl font-black gradient-text">РУЛЕТКА</h1>
        <p className="text-white/40 text-xs mt-1">
          {room ? (
            <>
              Комната <span className="text-neon-cyan font-mono">{room.id.slice(0, 8)}</span>
              {balance != null && (
                <>
                  {" · "}
                  <CoinIcon size={12} className="inline text-neon-purple" /> {balance}
                </>
              )}
            </>
          ) : (
            "Нет комнаты"
          )}
        </p>
      </div>

      {(error || info || roomFull) && (
        <GlassCard className="text-sm py-3">
          {error && <p className="text-red-400">{error}</p>}
          {info && <p className="text-neon-cyan">{info}</p>}
          {roomFull && (
            <div className="mt-2 flex flex-col gap-2">
              <p className="text-white/70">Стол занят. Создайте новую игру:</p>
              <NeonButton size="sm" onClick={createNewGame}>
                Новая игра
              </NeonButton>
            </div>
          )}
        </GlassCard>
      )}

      {/* Casino layout: wheel left / table right (stacks on narrow screens) */}
      <div className="flex flex-col lg:flex-row gap-3 items-stretch">
        {/* WHEEL */}
        <GlassCard glow className="lg:w-[42%] flex flex-col items-center py-4">
          <div className="relative w-56 h-56 sm:w-64 sm:h-64">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1 z-10 text-amber-300 drop-shadow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="12 2 2 22 22 22" />
              </svg>
            </div>
            <motion.svg
              viewBox="0 0 200 200"
              className="w-full h-full"
              animate={{ rotate: wheelRot }}
              transition={{ duration: spinning ? 4 : 0, ease: [0.12, 0.7, 0.1, 1] }}
              style={{ filter: "drop-shadow(0 0 12px rgba(168,85,247,0.45))" }}
            >
              {WHEEL_ORDER.map((num, i) => {
                const angle = (360 / SECTORS) * i;
                const x1 = 100 + 95 * Math.cos(((angle - 90) * Math.PI) / 180);
                const y1 = 100 + 95 * Math.sin(((angle - 90) * Math.PI) / 180);
                const x2 = 100 + 95 * Math.cos(((angle + 360 / SECTORS - 90) * Math.PI) / 180);
                const y2 = 100 + 95 * Math.sin(((angle + 360 / SECTORS - 90) * Math.PI) / 180);
                const c = numberColor(num);
                const fill = c === "red" ? "#b91c1c" : c === "black" ? "#0b1220" : "#15803d";
                const mid = angle + 360 / SECTORS / 2 - 90;
                const tx = 100 + 68 * Math.cos((mid * Math.PI) / 180);
                const ty = 100 + 68 * Math.sin((mid * Math.PI) / 180);
                return (
                  <g key={num}>
                    <path
                      d={`M100 100 L ${x1} ${y1} A 95 95 0 0 1 ${x2} ${y2} Z`}
                      fill={fill}
                      stroke="#334155"
                      strokeWidth="0.4"
                    />
                    <text
                      x={tx}
                      y={ty}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize="7"
                      fill="#fff"
                      fontWeight="700"
                    >
                      {num}
                    </text>
                  </g>
                );
              })}
              <circle cx="100" cy="100" r="18" fill="#0f0f1e" stroke="#a855f7" strokeWidth="2" />
            </motion.svg>
          </div>

          <div className="h-12 flex items-center justify-center mt-2">
            <AnimatePresence mode="wait">
              {result && !spinning && (
                <motion.div
                  key={result.number}
                  initial={{ scale: 0.6, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="flex items-center gap-3"
                >
                  <div
                    className="w-11 h-11 rounded-full flex items-center justify-center text-lg font-black text-white border border-white/20"
                    style={{
                      background:
                        result.color === "red"
                          ? "#dc2626"
                          : result.color === "black"
                            ? "#1a1a2e"
                            : "#16a34a",
                    }}
                  >
                    {result.number}
                  </div>
                  {payout != null && (
                    <span
                      className={`text-lg font-bold ${payout > 0 ? "text-emerald-400" : "text-rose-400"}`}
                    >
                      {payout > 0 ? `+${payout}` : payout} 🪙
                    </span>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </GlassCard>

        {/* BETTING TABLE */}
        <GlassCard className="flex-1 !p-3 sm:!p-4">
          <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
            <span className="text-white/60 text-xs uppercase tracking-wide">Стол (европейский)</span>
            <div className="flex items-center gap-1 flex-wrap">
              {CHIP_AMOUNTS.map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => {
                    setChip(a);
                    haptic("light");
                  }}
                  className={`w-9 h-9 rounded-full text-xs font-black border transition ${
                    chip === a
                      ? "bg-amber-400 text-black border-amber-200 scale-110"
                      : "bg-amber-500/20 text-amber-200 border-amber-500/40"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl overflow-hidden border border-emerald-700/40 bg-gradient-to-br from-emerald-950/80 to-emerald-900/40 p-2">
            {/* 0 */}
            <div className="flex gap-1 mb-1">
              <button
                type="button"
                onClick={() => addBet("number", 0)}
                className="relative flex-1 py-3 rounded-md bg-emerald-600 text-white font-black text-sm active:scale-95"
              >
                0
                <ChipBadge n={amountOn("number", 0)} />
              </button>
            </div>

            {/* numbers grid: display as 3 columns visually (1 2 3 / 4 5 6 ...) */}
            <div className="grid grid-cols-3 gap-1">
              {BOARD_ROWS.flatMap((row) =>
                row.map((n) => {
                  const c = numberColor(n);
                  const bg = c === "red" ? "bg-red-700" : "bg-zinc-900";
                  return (
                    <button
                      key={n}
                      type="button"
                      onClick={() => addBet("number", n)}
                      className={`relative py-2.5 rounded-md ${bg} text-white text-sm font-bold border border-white/10 active:scale-95`}
                    >
                      {n}
                      <ChipBadge n={amountOn("number", n)} />
                    </button>
                  );
                })
              )}
            </div>

            {/* columns */}
            <div className="grid grid-cols-3 gap-1 mt-1">
              {([1, 2, 3] as const).map((col) => (
                <button
                  key={`col-${col}`}
                  type="button"
                  onClick={() => addBet("column", col)}
                  className="relative py-2 rounded-md bg-emerald-800/70 text-white/90 text-[11px] font-semibold border border-white/10"
                >
                  2:1 кол.{col}
                  <ChipBadge n={amountOn("column", col)} />
                </button>
              ))}
            </div>

            {/* dozens */}
            <div className="grid grid-cols-3 gap-1 mt-1">
              {(
                [
                  [1, "1–12"],
                  [2, "13–24"],
                  [3, "25–36"],
                ] as const
              ).map(([d, label]) => (
                <button
                  key={`dz-${d}`}
                  type="button"
                  onClick={() => addBet("dozen", d)}
                  className="relative py-2 rounded-md bg-emerald-800/50 text-white/90 text-[11px] font-semibold border border-white/10"
                >
                  {label}
                  <ChipBadge n={amountOn("dozen", d)} />
                </button>
              ))}
            </div>

            {/* outside bets */}
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-1 mt-1">
              <button
                type="button"
                onClick={() => addBet("highlow", "low")}
                className="relative py-2 rounded-md bg-emerald-900/80 text-white text-[11px] font-bold border border-white/10"
              >
                1–18
                <ChipBadge n={amountOn("highlow", "low")} />
              </button>
              <button
                type="button"
                onClick={() => addBet("parity", "even")}
                className="relative py-2 rounded-md bg-emerald-900/80 text-white text-[11px] font-bold border border-white/10"
              >
                Чёт
                <ChipBadge n={amountOn("parity", "even")} />
              </button>
              <button
                type="button"
                onClick={() => addBet("color", "red")}
                className="relative py-2 rounded-md bg-red-700 text-white text-[11px] font-bold"
              >
                Красн
                <ChipBadge n={amountOn("color", "red")} />
              </button>
              <button
                type="button"
                onClick={() => addBet("color", "black")}
                className="relative py-2 rounded-md bg-zinc-900 text-white text-[11px] font-bold border border-white/20"
              >
                Чёрн
                <ChipBadge n={amountOn("color", "black")} />
              </button>
              <button
                type="button"
                onClick={() => addBet("parity", "odd")}
                className="relative py-2 rounded-md bg-emerald-900/80 text-white text-[11px] font-bold border border-white/10"
              >
                Нечет
                <ChipBadge n={amountOn("parity", "odd")} />
              </button>
              <button
                type="button"
                onClick={() => addBet("highlow", "high")}
                className="relative py-2 rounded-md bg-emerald-900/80 text-white text-[11px] font-bold border border-white/10"
              >
                19–36
                <ChipBadge n={amountOn("highlow", "high")} />
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between mt-3 gap-2 flex-wrap">
            <p className="text-white/60 text-sm">
              Ставка: <span className="text-amber-300 font-bold">{pendingTotal}</span> 🪙
            </p>
            <div className="flex gap-2">
              <NeonButton variant="cyan" size="sm" disabled={spinning || pending.length === 0} onClick={clearBets}>
                Сброс
              </NeonButton>
              <NeonButton variant="pink" size="lg" disabled={spinning || pending.length === 0} onClick={handleSpin}>
                {spinning ? "Крутится…" : "КРУТИТЬ"}
              </NeonButton>
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="flex justify-center gap-2 pb-4">
        <NeonButton variant="cyan" size="sm" onClick={() => goBackOrClose("/webapp/?page=casino")}>
          <span className="flex items-center gap-2">
            <BackIcon size={16} /> Назад
          </span>
        </NeonButton>
        <NeonButton variant="purple" size="sm" onClick={createNewGame}>
          Новая игра
        </NeonButton>
      </div>
    </div>
  );
}
