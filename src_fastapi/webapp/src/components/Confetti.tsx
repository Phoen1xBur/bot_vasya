import { useMemo } from "react";
import { motion } from "framer-motion";

interface ConfettiProps {
  count?: number;
  duration?: number;
}

const COLORS = ["#a855f7", "#06b6d4", "#ec4899", "#22c55e", "#f59e0b", "#ef4444"];

export default function Confetti({ count = 60, duration = 3 }: ConfettiProps) {
  const pieces = useMemo(() => {
    return Array.from({ length: count }).map((_, i) => {
      const left = Math.random() * 100;
      const delay = Math.random() * 0.5;
      const size = 6 + Math.random() * 8;
      const color = COLORS[i % COLORS.length];
      const rotate = Math.random() * 360;
      return { left, delay, size, color, rotate, id: i };
    });
  }, [count]);

  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      {pieces.map((p) => (
        <motion.div
          key={p.id}
          initial={{ y: -20, opacity: 1, rotate: p.rotate }}
          animate={{
            y: "110vh",
            opacity: [1, 1, 0],
            rotate: p.rotate + 360,
          }}
          transition={{
            duration: duration,
            delay: p.delay,
            ease: "easeIn",
            repeat: Infinity,
            repeatDelay: 0.5,
          }}
          style={{
            position: "absolute",
            left: `${p.left}%`,
            width: `${p.size}px`,
            height: `${p.size * 1.5}px`,
            backgroundColor: p.color,
            borderRadius: "2px",
          }}
        />
      ))}
    </div>
  );
}
