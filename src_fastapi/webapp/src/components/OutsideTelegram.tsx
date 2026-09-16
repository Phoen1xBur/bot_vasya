import GlassCard from "./GlassCard";

export default function OutsideTelegram() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center p-6">
      <GlassCard glow className="max-w-md w-full text-center">
        <h1 className="text-2xl font-bold mb-3">Откройте в Telegram</h1>
        <p className="text-white/70 mb-4 leading-relaxed">
          Эта страница — часть WebApp бота Васи и работает только внутри Telegram.
          Зайдите в чат с ботом и откройте игру или раздел оттуда.
        </p>
        <p className="text-white/50 text-sm">
          Если вы просто открыли ссылку в браузере — так и задумано: игровые комнаты
          снаружи Telegram недоступны.
        </p>
      </GlassCard>
    </div>
  );
}
