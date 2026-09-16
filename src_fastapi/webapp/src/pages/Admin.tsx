import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api, ApiError } from "../api/client";
import type { AdCampaign, AdminStats, AdminPrices, Payment } from "../types";
import { haptic, hapticNotify } from "../lib/telegram";
import { soundClick } from "../lib/sound";
import GlassCard from "../components/GlassCard";
import NeonButton from "../components/NeonButton";
import {
  ShieldIcon, ChartIcon, TagIcon, PaymentIcon,
  CheckIcon, XIcon, AdIcon, BackIcon,
} from "../components/icons";

type Tab = "campaigns" | "stats" | "prices" | "payments";

export default function Admin() {
  const [tab, setTab] = useState<Tab>("campaigns");
  const [denied, setDenied] = useState(false);
  const [deniedMsg, setDeniedMsg] = useState("");

  useEffect(() => {
    // Test access by fetching stats; admin routes require admin
    api.getAdminStats().catch((e) => {
      if (e instanceof ApiError && (e.status === 403 || e.status === 401)) {
        setDenied(true);
        setDeniedMsg(e.message || "Доступ только для администраторов");
      }
    });
  }, []);

  if (denied) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 gap-4">
        <GlassCard glow className="max-w-md text-center py-12">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200 }}
            className="w-16 h-16 mx-auto rounded-full bg-red-500/20 flex items-center justify-center mb-4"
          >
            <ShieldIcon size={32} className="text-red-400" />
          </motion.div>
          <h2 className="text-2xl font-bold text-red-400">Доступ запрещён</h2>
          <p className="text-white/50 text-sm mt-2">{deniedMsg}</p>
        </GlassCard>
        <NeonButton variant="cyan" size="sm" onClick={() => window.history.back()}>
          <span className="flex items-center gap-2"><BackIcon size={16} /> Назад</span>
        </NeonButton>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: typeof ShieldIcon }[] = [
    { id: "campaigns", label: "Заявки", icon: AdIcon },
    { id: "stats", label: "Статистика", icon: ChartIcon },
    { id: "prices", label: "Цены", icon: TagIcon },
    { id: "payments", label: "Платежи", icon: PaymentIcon },
  ];

  return (
    <div className="min-h-screen p-4 pt-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-4">
        <h1 className="text-3xl font-black gradient-text flex items-center justify-center gap-2">
          <ShieldIcon size={28} /> АДМИН
        </h1>
      </motion.div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 max-w-2xl mx-auto overflow-x-auto">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => { setTab(t.id); haptic("light"); soundClick(); }}
              className={`flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${tab === t.id ? "bg-gradient-to-r from-neon-purple to-purple-700 text-white" : "glass text-white/50"}`}
            >
              <Icon size={16} />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="max-w-2xl mx-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            {tab === "campaigns" && <CampaignsTab />}
            {tab === "stats" && <StatsTab />}
            {tab === "prices" && <PricesTab />}
            {tab === "payments" && <PaymentsTab />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

// ---- Campaigns Tab ----
function CampaignsTab() {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const status = filter === "all" ? undefined : filter;
      // Try the ads campaigns endpoint with status filter
      const res = await api.getCampaigns(status);
      setCampaigns(res.campaigns);
    } catch {
      // Fallback to admin campaigns endpoint (no filter)
      try {
        const res = await api.getAdminCampaigns();
        const filtered = filter === "all" ? res.campaigns : res.campaigns.filter((c) => c.status === filter);
        setCampaigns(filtered);
      } catch {
        // ignore
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filter]);

  const handleApprove = async (id: string) => {
    haptic("medium");
    try {
      await api.approveCampaign(id, comment);
      hapticNotify("success");
      setActionId(null);
      setComment("");
      load();
    } catch (e) {
      hapticNotify("error");
    }
  };

  const handleReject = async (id: string) => {
    haptic("medium");
    try {
      await api.rejectCampaign(id, comment);
      hapticNotify("success");
      setActionId(null);
      setComment("");
      load();
    } catch {
      hapticNotify("error");
    }
  };

  const statusColors: Record<string, string> = {
    ai_pending: "bg-amber-500/20 text-amber-400",
    ai_approved: "bg-cyan-500/20 text-cyan-400",
    ai_rejected: "bg-red-500/20 text-red-400",
    approved: "bg-green-500/20 text-green-400",
    rejected: "bg-red-500/20 text-red-400",
    sent: "bg-blue-500/20 text-blue-400",
  };

  const filters = ["all", "ai_pending", "ai_approved", "ai_rejected", "approved", "rejected"];

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Filters */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => { setFilter(f); haptic("light"); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap ${filter === f ? "bg-neon-purple text-white" : "glass text-white/50"}`}
          >
            {f}
          </button>
        ))}
      </div>

      {campaigns.length === 0 && (
        <GlassCard className="text-center py-8 text-white/40">Нет заявок</GlassCard>
      )}

      {campaigns.map((c) => (
        <motion.div
          key={c.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <GlassCard>
            <div className="flex items-start justify-between gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${statusColors[c.status] ?? "glass"}`}>
                {c.status}
              </span>
              <span className="text-white/40 text-xs">{new Date(c.created_at ?? "").toLocaleString("ru-RU")}</span>
            </div>
            <p className="text-sm text-white/80 mb-1">{c.text}</p>
            <a href={c.link} target="_blank" rel="noopener" className="text-neon-cyan text-xs hover:underline">{c.link}</a>
            <div className="flex gap-3 text-xs text-white/50 mt-2">
              <span>🎯 {c.target_unique_users}</span>
              <span>💰 {(c.price / 100).toLocaleString("ru-RU")} ₽</span>
              <span>👤 {c.advertiser_id}</span>
              {c.contact && <span>📞 {c.contact}</span>}
            </div>

            {/* AI verdict */}
            {c.ai_verdict && (
              <div className="glass rounded-lg p-2 mt-2 text-xs">
                <p className="text-white/50 mb-1">AI-вердикт:</p>
                <pre className="text-white/70 whitespace-pre-wrap">{JSON.stringify(c.ai_verdict, null, 1)}</pre>
              </div>
            )}

            {/* Admin comment */}
            {c.admin_comment && (
              <p className="text-white/50 text-xs mt-2">Админ: {c.admin_comment}</p>
            )}

            {/* Action buttons */}
            {(c.status === "ai_approved" || c.status === "ai_pending") && (
              <div className="mt-3">
                {actionId === c.id ? (
                  <div className="flex flex-col gap-2">
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder="Комментарий..."
                      rows={2}
                      className="glass rounded-lg px-3 py-2 text-xs outline-none resize-none"
                    />
                    <div className="flex gap-2">
                      <NeonButton variant="green" size="sm" onClick={() => handleApprove(c.id)}>
                        <span className="flex items-center gap-1"><CheckIcon size={14} /> Одобрить</span>
                      </NeonButton>
                      <NeonButton variant="danger" size="sm" onClick={() => handleReject(c.id)}>
                        <span className="flex items-center gap-1"><XIcon size={14} /> Отклонить</span>
                      </NeonButton>
                      <NeonButton variant="cyan" size="sm" onClick={() => { setActionId(null); setComment(""); }}>
                        Отмена
                      </NeonButton>
                    </div>
                  </div>
                ) : (
                  <NeonButton variant="purple" size="sm" onClick={() => { setActionId(c.id); setComment(""); }}>
                    Действие
                  </NeonButton>
                )}
              </div>
            )}
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}

// ---- Stats Tab ----
function StatsTab() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAdminStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" /></div>;
  if (!stats) return <GlassCard className="text-center text-white/40">Нет данных</GlassCard>;

  const statCards = [
    { label: "Доход", value: `${(stats.revenue_kopecks / 100).toLocaleString("ru-RU")} ₽`, gradient: "from-neon-green to-emerald-600" },
    { label: "Активные подписки", value: stats.active_subscriptions, gradient: "from-neon-purple to-purple-700" },
    { label: "Донаты", value: `${(stats.total_donations_kopecks / 100).toLocaleString("ru-RU")} ₽`, gradient: "from-neon-cyan to-blue-700" },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {statCards.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
            <GlassCard className="text-center">
              <p className="text-white/50 text-xs uppercase tracking-wide">{s.label}</p>
              <p className={`text-2xl font-black bg-gradient-to-r ${s.gradient} bg-clip-text text-transparent mt-1`}>{s.value}</p>
            </GlassCard>
          </motion.div>
        ))}
      </div>

      <GlassCard>
        <h3 className="font-bold text-sm mb-3 text-neon-cyan">Заявки на рекламу</h3>
        <div className="space-y-2">
          {Object.entries(stats.ad_campaigns_by_status).map(([status, count]) => (
            <div key={status} className="flex items-center justify-between text-sm">
              <span className="text-white/60">{status}</span>
              <span className="font-bold">{count}</span>
            </div>
          ))}
          {Object.keys(stats.ad_campaigns_by_status).length === 0 && (
            <p className="text-white/40 text-sm text-center">Нет данных</p>
          )}
        </div>
      </GlassCard>

      {stats.economy_balance && typeof stats.economy_balance === "object" ? (
        <GlassCard>
          <h3 className="font-bold text-sm mb-3 text-neon-cyan">Баланс экономики</h3>
          <pre className="text-white/70 text-xs whitespace-pre-wrap">
            {JSON.stringify(stats.economy_balance, null, 2)}
          </pre>
        </GlassCard>
      ) : null}
    </div>
  );
}

// ---- Prices Tab ----
function PricesTab() {
  const [prices, setPrices] = useState<AdminPrices | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getPrices()
      .then((p) => {
        setPrices(p);
        setEdit({
          sub_vip: String(p.sub_vip),
          sub_premium: String(p.sub_premium),
          sub_elite: String(p.sub_elite),
          ad_per_1000: String(p.ad_per_1000),
          ai_check_enabled: String(p.ai_check_enabled),
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    haptic("medium");
    try {
      await api.setPrices(edit);
      hapticNotify("success");
    } catch {
      hapticNotify("error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" /></div>;
  if (!prices) return <GlassCard className="text-center text-white/40">Нет данных</GlassCard>;

  const fields: { key: keyof AdminPrices; label: string; hint?: string }[] = [
    { key: "sub_vip", label: "VIP (коп.)" },
    { key: "sub_premium", label: "Premium (коп.)" },
    { key: "sub_elite", label: "Elite (коп.)" },
    { key: "ad_per_1000", label: "Реклама за 1000 (коп.)" },
    { key: "ai_check_enabled", label: "AI проверка (true/false)" },
  ];

  return (
    <div className="flex flex-col gap-3">
      <GlassCard>
        <h3 className="font-bold text-sm mb-3 text-neon-cyan">Редактирование цен</h3>
        <div className="space-y-3">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="text-white/50 text-xs block mb-1">{f.label}</label>
              <input
                type="text"
                value={edit[f.key] ?? ""}
                onChange={(e) => { setEdit({ ...edit, [f.key]: e.target.value }); haptic("light"); }}
                className="w-full glass rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-neon-purple"
              />
            </div>
          ))}
        </div>
        <div className="mt-4">
          <NeonButton variant="purple" onClick={handleSave} disabled={saving} className="w-full">
            {saving ? "Сохранение..." : "СОХРАНИТЬ"}
          </NeonButton>
        </div>
      </GlassCard>
    </div>
  );
}

// ---- Payments Tab ----
function PaymentsTab() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getPayments(50)
      .then((r) =>
        setPayments(
          (r.payments || []).filter(
            (p) => p.status !== "NEW" && p.status !== "PENDING"
          )
        )
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-neon-purple/30 border-t-neon-purple rounded-full animate-spin" /></div>;

  const statusColors: Record<string, string> = {
    confirmed: "text-green-400",
    pending: "text-amber-400",
    failed: "text-red-400",
    cancelled: "text-red-400",
  };

  return (
    <div className="flex flex-col gap-2">
      {payments.length === 0 && <GlassCard className="text-center text-white/40">Нет платежей</GlassCard>}
      {payments.map((p, i) => (
        <motion.div key={p.order_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
          <GlassCard className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-mono truncate">{p.order_id}</p>
              <p className="text-white/40 text-xs">ID: {p.user_id} · {p.payment_type}</p>
            </div>
            <div className="text-right">
              <p className="font-bold text-sm">{(p.amount / 100).toLocaleString("ru-RU")} ₽</p>
              <p className={`text-xs ${statusColors[p.status] ?? "text-white/50"}`}>{p.status}</p>
            </div>
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}
