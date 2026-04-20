-- ═══════════════════════════════════════════════════════════════════════
-- NECHH ROBOTICS — Supabase SQL Şeması
-- Supabase Dashboard → SQL Editor'de bu kodu çalıştır.
-- ═══════════════════════════════════════════════════════════════════════

-- ── Ana abone tablosu ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscribers (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email                   text UNIQUE NOT NULL,
    telegram_username       text,
    telegram_user_id        bigint,           -- Telegram numeric ID (bot'tan gelir)
    country                 text,
    plan                    text DEFAULT 'monthly' CHECK (plan IN ('monthly','quarterly','annual')),
    subscription_status     text DEFAULT 'pending' CHECK (subscription_status IN ('pending','active','expired','cancelled','banned')),
    subscription_start      timestamptz,
    subscription_end        timestamptz,
    payment_tx_id           text,             -- Kripto TX hash
    payment_method          text,             -- 'crypto' | 'stripe'
    last_payment_at         timestamptz,
    last_payment_reminder_at timestamptz,
    warning_count           int DEFAULT 0,    -- Kural ihlali uyarı sayısı
    notes                   text,             -- Admin notu
    created_at              timestamptz DEFAULT now(),
    updated_at              timestamptz DEFAULT now()
);

-- ── Ödeme geçmişi ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id   uuid REFERENCES subscribers(id) ON DELETE CASCADE,
    amount_usd      numeric(10,2) NOT NULL,
    plan            text,
    tx_id           text,
    method          text,
    status          text DEFAULT 'completed' CHECK (status IN ('pending','completed','failed','refunded')),
    period_start    timestamptz,
    period_end      timestamptz,
    created_at      timestamptz DEFAULT now()
);

-- ── Kural ihlali log ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS violations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id   uuid REFERENCES subscribers(id) ON DELETE CASCADE,
    violation_type  text NOT NULL,  -- 'spam','sharing_signals','abusive','other'
    description     text,
    action_taken    text,           -- 'warning','mute','kick','ban'
    created_at      timestamptz DEFAULT now()
);

-- ── Sistem logları ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_events (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  text NOT NULL,  -- 'cron_run','payment_received','user_expired', etc.
    details     jsonb,
    created_at  timestamptz DEFAULT now()
);

-- ── İndeksler ──────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(subscription_status);
CREATE INDEX IF NOT EXISTS idx_subscribers_end    ON subscribers(subscription_end);
CREATE INDEX IF NOT EXISTS idx_payments_subscriber ON payments(subscriber_id);
CREATE INDEX IF NOT EXISTS idx_violations_subscriber ON violations(subscriber_id);

-- ── Row Level Security ─────────────────────────────────────────────────
ALTER TABLE subscribers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments      ENABLE ROW LEVEL SECURITY;
ALTER TABLE violations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_events ENABLE ROW LEVEL SECURITY;

-- Sadece service_role okuyabilir (anon key ile frontend erişemez)
CREATE POLICY "service_only" ON subscribers   USING (auth.role() = 'service_role');
CREATE POLICY "service_only" ON payments      USING (auth.role() = 'service_role');
CREATE POLICY "service_only" ON violations    USING (auth.role() = 'service_role');
CREATE POLICY "service_only" ON system_events USING (auth.role() = 'service_role');

-- ── Otomatik updated_at ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscribers_updated_at
    BEFORE UPDATE ON subscribers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Yardımcı view: admin paneli için ──────────────────────────────────
CREATE OR REPLACE VIEW admin_dashboard AS
SELECT
    subscription_status,
    COUNT(*) AS count,
    COUNT(*) FILTER (WHERE subscription_end < now()) AS expired_count,
    COUNT(*) FILTER (WHERE subscription_end BETWEEN now() AND now() + interval '7 days') AS expiring_soon,
    SUM(CASE WHEN plan = 'monthly' AND subscription_status = 'active' THEN 55
             WHEN plan = 'quarterly' AND subscription_status = 'active' THEN 45
             WHEN plan = 'annual' AND subscription_status = 'active' THEN 35
             ELSE 0 END) AS mrr_contribution
FROM subscribers
GROUP BY subscription_status;
