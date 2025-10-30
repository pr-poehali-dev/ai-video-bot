-- Добавление поля temp_data для хранения промежуточных данных в JSON
ALTER TABLE t_p62125649_ai_video_bot.user_states 
ADD COLUMN IF NOT EXISTS temp_data JSONB;

COMMENT ON COLUMN t_p62125649_ai_video_bot.user_states.temp_data 
IS 'JSON для хранения промежуточных данных (сцены storyboard и т.д.)';