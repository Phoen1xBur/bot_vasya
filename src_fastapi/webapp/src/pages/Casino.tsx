import { motion } from "framer-motion";
import { getUrlParams, haptic } from "../lib/telegram";
import { soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import { DiceIcon, SlotsIcon, GameIcon, BackIcon } from "../components/icons";

const games = [
  {
    id: "roulette",
    title: "Рулетка",
    desc: "Казино-рулетка с ставками на цвет, число, чёт/нечет",
    icon: DiceIcon,
    gradient: "from-red-500 to-rose-700",
    url: (chatId: string | null) => `/webapp/?page=roulette${chatId ? `&chat_id=${chatId}` : ""}`,
  },
  {
    id: "slots",
    title: "Слоты",
    desc: "Крути барабаны — лови джекпот!",
    icon: SlotsIcon,
    gradient: "from-amber-400 to-orange-600",
    url: (chatId: string | null) => `/webapp/?page=slots${chatId ? `&chat_id=${chatId}` : ""}`,
  },
  {
    id: "ttt",
    title: "Крестики-нолики",
    desc: "Дуэль 1×1 на васякоины",
    icon: GameIcon,
    gradient: "from-neon-purple to-purple-700",
    url: (chatId: string | null) => `/webapp/?page=ttt${chatId ? `&chat_id=${chatId}` : ""}`,
  },
];

export default function Casino() {
  const params = getUrlParams();

  return (
    <div className="flex flex-col items-center min-h-screen p-4 pt-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md text-center mb-6"
      >
        <h1 className="text-4xl font-black gradient-text neon-text">КАЗИНО</h1>
        <p className="text-white/50 text-sm mt-1">Выбери игру и испытай удачу</p>
      </motion.div>

      <div className="w-full max-w-md flex flex-col gap-4">
        {games.map((g, i) => {
          const Icon = g.icon;
          return (
            <motion.a
              key={g.id}
              href={g.url(params.chat_id)}
              initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => { haptic("light"); soundClick(); }}
            >
              <GlassCard className="flex items-center gap-4 cursor-pointer hover:neon-glow transition-all">
                <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${g.gradient} flex items-center justify-center flex-shrink-0`}>
                  <Icon size={28} className="text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-lg">{g.title}</h3>
                  <p className="text-white/50 text-xs">{g.desc}</p>
                </div>
                <BackIcon size={20} className="text-white/30 rotate-180" />
              </GlassCard>
            </motion.a>
          );
        })}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-8"
      >
        <NeonButton variant="cyan" size="sm" onClick={() => window.history.back()}>
          <span className="flex items-center gap-2">
            <BackIcon size={16} />
            Назад
          </span>
        </NeonButton>
      </motion.div>
    </div>
  );
}
