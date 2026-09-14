import { motion, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";

interface GlassCardProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  glow?: boolean;
  className?: string;
}

export default function GlassCard({ children, glow, className = "", ...props }: GlassCardProps) {
  return (
    <motion.div
      className={`glass rounded-2xl p-5 ${glow ? "neon-glow" : ""} ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
}
