CREATE TABLE IF NOT EXISTS t_p62125649_ai_video_bot.admin_actions (
    action_id SERIAL PRIMARY KEY,
    admin_username VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_user_id BIGINT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_admin_actions_target_user ON t_p62125649_ai_video_bot.admin_actions(target_user_id);
CREATE INDEX idx_admin_actions_created_at ON t_p62125649_ai_video_bot.admin_actions(created_at);