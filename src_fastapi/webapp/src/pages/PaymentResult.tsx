import GlassCard from "../components/GlassCard";

export default function PaymentResult() {
  const status = new URLSearchParams(window.location.search).get("status") || "success";
  const success = status === "success";

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-6">
      <GlassCard glow className="max-w-md w-full text-center space-y-4">
        <h1 className="text-2xl font-bold">
          {success ? "Оплата прошла" : "Оплата не завершена"}
        </h1>
        <p className="text-white/70 leading-relaxed">
          {success
            ? "Если вы оформляли подписку — VIP/Premium/Elite активируется автоматически. Вернитесь в Telegram к боту Вася и откройте профиль или напишите /subscribe."
            : "Платёж не подтверждён. Можно вернуться в Telegram и попробовать снова через /subscribe."}
        </p>
        <p className="text-white/50 text-sm">
          Эту страницу банк открывает в обычном браузере — так и должно быть. Mini App с оплатой не нужен.
        </p>
        <a
          className="inline-block mt-2 px-4 py-2 rounded-xl bg-gradient-to-r from-neon-purple to-purple-700 font-semibold"
          href="https://t.me/vasya_fun_bot"
        >
          Открыть бота в Telegram
        </a>
      </GlassCard>
    </div>
  );
}
