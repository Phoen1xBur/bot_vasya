import { motion, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";
import { haptic } from "../lib/telegram";
import { soundClick } from "../lib/sound";

interface NeonButtonProps extends Omit<HTMLMotionProps<"button">, "ref"> {
  children: ReactNode;
  variant?: "purple" | "cyan" | "pink" | "green" | "danger";
  size?: "sm" | "md" | "lg";
}

const variants = {
  purple: "from-neon-purple to-purple-600",
  cyan: "from-neon-cyan to-blue-600",
  pink: "from-neon-pink to-rose-600",
  green: "from-neon-green to-emerald-600",
  danger: "from-red-500 to-red-700",
};

const sizes = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-base",
  lg: "px-8 py-4 text-lg",
};

export default function NeonButton({
  children,
  variant = "purple",
  size = "md",
  className = "",
  onClick,
  disabled,
  ...props
}: NeonButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: 0.92 }}
      whileHover={{ scale: disabled ? 1 : 1.03 }}
      className={`
        relative rounded-xl font-semibold text-white
        bg-gradient-to-r ${variants[variant]}
        shadow-lg overflow-hidden
        disabled:opacity-40 disabled:cursor-not-allowed
        transition-shadow
        ${sizes[size]} ${className}
      `}
      onClick={(e) => {
        if (disabled) return;
        haptic("medium");
        soundClick();
        onClick?.(e);
      }}
      disabled={disabled}
      {...props}
    >
      <span className="relative z-10">{children}</span>
      <motion.span
        className="absolute inset-0 bg-white/20"
        initial={{ x: "-100%" }}
        whileHover={{ x: "100%" }}
        transition={{ duration: 0.4 }}
      />
    </motion.button>
  );
}
