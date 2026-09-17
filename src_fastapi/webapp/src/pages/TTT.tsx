import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError } from "../api/client";
import type { RoomState } from "../types";
import { getUrlParams, getCurrentUserId, haptic, hapticNotify, goBack } from "../lib/telegram";
import { soundWin, soundLose, soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import Confetti from "../components/Confetti";
import { BackIcon } from "../components/icons";

const WIN_LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6],
];

function getWinningLine(board: string): number[] | null {
  for (const line of WIN_LINES) {
    const [a, b, c] = line;
    if (board[a] !== " " && board[a] === board[b] && board[a] === board[c]) {
      return line;
    }
  }
  return null;
}

export default function TTT() {
  const params = getUrlParams();
  const chatId = params.chat_id ? parseInt(params.chat_id) : null;
  const myId = getCurrentUserId();
  const [room, setRoom] = useState<RoomState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const boot = async () => {
      setCreating(true);
      setError(null);
      try {
        if (params.room) {
          const r = await api.getRoom(params.room);
          if (cancelled) return;
          setRoom(r as RoomState);
          if (
            myId &&
            r.initiator_id !== myId &&
            r.target_id !== myId
          ) {
            setError("Комната не для вас — дуэль только для двух игроков.");
            return;
          }

          // Opponent accepts waiting duel
          if (r.status === "waiting" && myId && myId === r.target_id) {
            try {
              const joined = await api.joinRoom(r.id, {});
              if (!cancelled) setRoom(joined as RoomState);
            } catch {
              // already active or not allowed — keep waiting view
            }
          }
          return;
        }
        const targetId = params.target ? parseInt(params.target, 10) : NaN;
        if (Number.isFinite(targetId) && targetId > 0) {
          const r = await api.createRoom({
            game_type: "ttt",
            chat_id: chatId ?? myId,
            target_id: targetId,
            bet: 0,
          });
          if (!cancelled) setRoom(r as RoomState);
          return;
        }
        setError(
          "Создайте дуэль в группе: мини-игры → крестики-нолики → тегните оппонента или ответьте на его сообщение."
        );
      } catch (e) {
        const msg =
          e instanceof ApiError
            ? (e.detail?.toString?.() ?? e.message)
            : e instanceof Error
              ? e.message
              : String(e);
        if (!cancelled) setError(msg);
      } finally {
        if (!cancelled) setCreating(false);
      }
    };
    void boot();
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll room state while waiting OR active — иначе второй игрок не видит ходы
  useEffect(() => {
    if (!room) return;
    if (room.status !== "waiting" && room.status !== "active") return;
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const r = await api.getRoom(room.id);
        setRoom(r as RoomState);
      } catch {
        // room may be expired
      }
    }, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [room?.id, room?.status]);

  const board: string = (room?.state as { board?: string } | null)?.board ?? "         ";
  const turn: string = (room?.state as { turn?: string } | null)?.turn ?? "X";
  const winnerId: number | null = (room?.state as { winner?: number } | null)?.winner ?? room?.winner_id ?? null;

  const isInitiator = room && myId === room.initiator_id;
  const isTarget = room && myId === room.target_id;
  const myMark = isInitiator ? "X" : isTarget ? "O" : null;
  const isMyTurn = room?.status === "active" && myMark === turn;
  const winningLine = winnerId && winnerId > 0 ? getWinningLine(board) : null;

  useEffect(() => {
    if (winnerId !== null && winnerId !== undefined && winnerId !== 0) {
      if (winnerId === myId) {
        hapticNotify("success");
        soundWin();
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 5000);
      } else {
        hapticNotify("warning");
        soundLose();
      }
    } else if (winnerId === 0) {
      hapticNotify("warning");
    }
  }, [winnerId]);

  const handleCellClick = async (cell: number) => {
    if (!room || !isMyTurn || busy) return;
    if (board[cell] !== " ") return;
    setBusy(true);
    haptic("light");
    soundClick();
    try {
      const res = await api.roomAction(room.id, { cell }) as Partial<RoomState> & { board?: string; turn?: string; status?: string };
      // Сразу применяем ответ action (board/turn), затем подтверждаем getRoom
      if (res && (res.board || res.turn || res.status)) {
        setRoom((prev) => {
          if (!prev) return prev;
          const state = { ...(prev.state as object), board: res.board ?? (prev.state as { board?: string })?.board, turn: res.turn ?? (prev.state as { turn?: string })?.turn };
          return { ...prev, state, status: (res.status as RoomState["status"]) ?? prev.status, winner_id: (res as { winner?: number }).winner ?? prev.winner_id };
        });
      }
      const updated = await api.getRoom(room.id);
      setRoom(updated as RoomState);
    } catch (e) {
      const msg = e instanceof ApiError ? (e.detail?.toString?.() ?? e.message) : e instanceof Error ? e.message : String(e);
      hapticNotify("error");
      setError(msg);
      setTimeout(() => setError(null), 3000);
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

  if (error && !room) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4 gap-4">
        <GlassCard className="max-w-md w-full text-center space-y-3">
          <p className="text-lg font-semibold">Крестики-нолики (дуэль)</p>
          <p className="text-sm text-white/70">
            Создайте дуэль в группе: мини-игры → крестики-нолики, затем тегните
            оппонента или ответьте на его сообщение. В комнату войдёте только вы двое.
          </p>
          <p className="text-red-400 text-sm">{error}</p>
        </GlassCard>
        <NeonButton variant="cyan" onClick={() => goBack()}>
          <span className="flex items-center gap-2"><BackIcon size={16} /> Назад</span>
        </NeonButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6 gap-4">
      {showConfetti && <Confetti />}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed top-16 left-1/2 -translate-x-1/2 z-50"
        >
          <div className="glass rounded-lg px-4 py-2 text-red-400 text-sm">{error}</div>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-black gradient-text">КРЕСТИКИ-НОЛИКИ</h1>
        <p className="text-white/50 text-xs mt-1">Дуэль 1×1</p>
      </motion.div>

      {room?.status === "waiting" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="w-full max-w-sm"
        >
          <GlassCard glow className="text-center py-8">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="w-10 h-10 border-2 border-neon-cyan/30 border-t-neon-cyan rounded-full mx-auto mb-4"
            />
            <p className="text-lg font-semibold">Ожидание соперника...</p>
            <p className="text-white/40 text-sm mt-1">Ваш ход: <span className="text-neon-purple font-bold">{myMark}</span></p>
          </GlassCard>
        </motion.div>
      )}

      {(room?.status === "active" || room?.status === "finished") && (
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="w-full max-w-xs">
          <GlassCard>
            <div className="text-center mb-4">
              {room?.status === "finished" ? (
                winnerId === 0 ? (
                  <p className="text-white/80 font-bold">Ничья</p>
                ) : winnerId === myId ? (
                  <p className="text-neon-green font-black">Победа</p>
                ) : (
                  <p className="text-red-400 font-bold">Поражение</p>
                )
              ) : isMyTurn ? (
                <p className="text-neon-green font-bold animate-pulse">Ваш ход ({myMark})</p>
              ) : (
                <p className="text-white/50">Ход соперника ({turn === myMark ? "..." : turn})</p>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {board.split("").map((cell, i) => (
                <motion.button
                  key={i}
                  whileTap={{ scale: 0.9 }}
                  disabled={!isMyTurn || cell !== " " || busy}
                  onClick={() => handleCellClick(i)}
                  className={`
                    aspect-square rounded-xl text-4xl font-black flex items-center justify-center
                    ${cell === " " && isMyTurn ? "glass hover:bg-white/10 cursor-pointer" : "glass"}
                    ${cell === "X" ? "text-neon-purple" : cell === "O" ? "text-neon-cyan" : ""}
                    ${winningLine?.includes(i) ? "bg-neon-green/20 ring-2 ring-neon-green" : ""}
                  `}
                >
                  <AnimatePresence mode="wait">
                    {cell !== " " && (
                      <motion.span
                        initial={{ scale: 0, rotate: -180 }}
                        animate={{ scale: 1, rotate: 0 }}
                        transition={{ type: "spring", stiffness: 200 }}
                      >
                        {cell}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </motion.button>
              ))}
            </div>
          </GlassCard>
        </motion.div>
      )}

      <AnimatePresence>
        {(room?.status === "finished" || room?.status === "expired" || room?.status === "cancelled") && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="w-full max-w-xs"
          >
            <GlassCard glow className="text-center py-4">
              {winnerId === 0 ? (
                <p className="text-2xl font-bold text-white/70">Ничья!</p>
              ) : winnerId === myId ? (
                <motion.p
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200 }}
                  className="text-3xl font-black gradient-text"
                >
                  ПОБЕДА! 🎉
                </motion.p>
              ) : (
                <p className="text-2xl font-bold text-red-400">Поражение 😔</p>
              )}
              <div className="mt-4">
                <NeonButton variant="cyan" onClick={() => goBack()}>
                  <span className="flex items-center gap-2"><BackIcon size={16} /> Закрыть</span>
                </NeonButton>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
