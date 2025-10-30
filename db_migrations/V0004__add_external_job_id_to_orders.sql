-- Добавление поля external_job_id для хранения ID задания от внешнего API
ALTER TABLE t_p62125649_ai_video_bot.orders 
ADD COLUMN IF NOT EXISTS external_job_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_orders_external_job_id 
ON t_p62125649_ai_video_bot.orders(external_job_id);

COMMENT ON COLUMN t_p62125649_ai_video_bot.orders.external_job_id 
IS 'ID задания от kie.ai API для отслеживания статуса генерации';