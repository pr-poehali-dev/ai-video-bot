-- Таблица для логирования всех платежных событий
CREATE TABLE IF NOT EXISTS t_p62125649_ai_video_bot.payment_logs (
    log_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES t_p62125649_ai_video_bot.users(user_id),
    payment_method TEXT NOT NULL, -- 'telegram_card', 'telegram_stars', 'yookassa'
    payment_status TEXT NOT NULL, -- 'pending', 'success', 'failed', 'cancelled'
    amount NUMERIC(10, 2), -- сумма в рублях или звёздах
    currency TEXT, -- 'RUB', 'XTR' (Telegram Stars)
    external_payment_id TEXT,
    telegram_update JSONB, -- полный update от Telegram
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Добавить поле payment_method в таблицу transactions
ALTER TABLE t_p62125649_ai_video_bot.transactions 
ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'yookassa';

-- Создать индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_payment_logs_user_id ON t_p62125649_ai_video_bot.payment_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_logs_status ON t_p62125649_ai_video_bot.payment_logs(payment_status);
CREATE INDEX IF NOT EXISTS idx_payment_logs_created_at ON t_p62125649_ai_video_bot.payment_logs(created_at);

-- Таблица для хранения статистики (для возможности сброса)
CREATE TABLE IF NOT EXISTS t_p62125649_ai_video_bot.stats_cache (
    stats_id SERIAL PRIMARY KEY,
    metric_name TEXT UNIQUE NOT NULL,
    metric_value NUMERIC DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Инициализация базовых метрик
INSERT INTO t_p62125649_ai_video_bot.stats_cache (metric_name, metric_value)
VALUES 
    ('total_revenue_offset', 0),
    ('total_orders_offset', 0),
    ('errors_count_offset', 0)
ON CONFLICT (metric_name) DO NOTHING;