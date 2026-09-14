import { motion } from "framer-motion";
import { useAppStore } from "../store/appStore";
import { soundClick } from "../lib/sound";
import { haptic } from "../lib/telegram";

export default function SoundToggle() {
  const muted = useAppStore((s) => s.muted);
  const toggleMute = useAppStore((s) => s.toggleMute);

  return (
    <motion.button
      whileTap={{ scale: 0.85 }}
      onClick={() => {
        haptic("light");
        soundClick();
        toggleMute();
      }}
      className="fixed top-4 right-4 z-40 w-10 h-10 rounded-full glass flex items-center justify-center"
      aria-label="Toggle sound"
    >
      {muted ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <line x1="23" y1="9" x2="17" y2="15" />
          <line x1="17" y1="9" x2="23" y2="15" />
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
        </svg>
      )}
    </motion.button>
  );
}
