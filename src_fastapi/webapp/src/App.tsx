import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { getUrlParams, initTelegram, applyTheme, isInsideTelegram, isTelegramOnlyPage, type PageName } from "./lib/telegram";
import OutsideTelegram from "./components/OutsideTelegram";
import { useAppStore } from "./store/appStore";
import { setMuted } from "./lib/sound";
import LoadingScreen from "./components/LoadingScreen";
import SoundToggle from "./components/SoundToggle";
import Profile from "./pages/Profile";
import TTT from "./pages/TTT";
import Roulette from "./pages/Roulette";
import Slots from "./pages/Slots";
import Casino from "./pages/Casino";
import Advertise from "./pages/Advertise";
import Admin from "./pages/Admin";
import PaymentResult from "./pages/PaymentResult";

const pageTransition = {
  initial: { opacity: 0, scale: 0.96 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 1.04 },
  transition: { duration: 0.3, ease: "easeOut" as const },
};

export default function App() {
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState<PageName>("profile");
  const [blocked, setBlocked] = useState(false);
  const muted = useAppStore((s) => s.muted);
  const setTheme = useAppStore((s) => s.setTheme);

  useEffect(() => {
    initTelegram();
    applyTheme();
    const tg = window.Telegram?.WebApp;
    if (tg?.colorScheme) setTheme(tg.colorScheme);
    const params = getUrlParams();
    setPage(params.page);
    if (params.page !== "payment" && isTelegramOnlyPage(params.page, params) && !isInsideTelegram()) {
      setBlocked(true);
    }
    const timer = setTimeout(() => setLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    setMuted(muted);
  }, [muted]);

  const renderPage = () => {
    switch (page) {
      case "profile": return <Profile />;
      case "ttt": return <TTT />;
      case "roulette": return <Roulette />;
      case "slots": return <Slots />;
      case "casino": return <Casino />;
      case "advertise": return <Advertise />;
      case "admin": return <Admin />;
      case "payment": return <PaymentResult />;
      default: return <Profile />;
    }
  };

  return (
    <div className="bg-mesh min-h-screen w-full relative">
      <SoundToggle />
      <AnimatePresence mode="wait">
        {loading ? (
          <motion.div key="loading" {...pageTransition}>
            <LoadingScreen />
          </motion.div>
        ) : blocked ? (
          <motion.div key="outside" {...pageTransition}>
            <OutsideTelegram />
          </motion.div>
        ) : (
          <motion.div key={page} {...pageTransition}>
            {renderPage()}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
