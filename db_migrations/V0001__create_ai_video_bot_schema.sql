-- AI Video Studio Bot Database Schema
-- Production-ready schema with all required tables

-- Users table: stores Telegram user data and balance
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 800 CHECK (balance >= 0),
    currency TEXT DEFAULT 'RUB',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);
CREATE INDEX IF NOT EXISTS idx_users_is_blocked ON users(is_blocked);

-- Orders table: tracks all video/preview generation orders
CREATE TYPE order_type_enum AS ENUM('preview','image-to-video','text-to-video','storyboard');
CREATE TYPE order_status_enum AS ENUM('pending','processing','completed','failed','cancelled');
CREATE TYPE quality_enum AS ENUM('standard','high');

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    order_type order_type_enum NOT NULL,
    prompt TEXT,
    aspect_ratio TEXT DEFAULT '16:9',
    duration INTEGER CHECK (duration IN (5, 10, 15, 25)),
    quality quality_enum DEFAULT 'standard',
    scenes_count INTEGER CHECK (scenes_count >= 2 AND scenes_count <= 15),
    parameters JSONB,
    status order_status_enum DEFAULT 'pending',
    cost INTEGER NOT NULL CHECK (cost > 0),
    result_url TEXT,
    task_id TEXT,
    video_sent BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 40,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_task_id ON orders(task_id);
CREATE INDEX IF NOT EXISTS idx_orders_processing ON orders(status, task_id);

-- Transactions table: financial operations log
CREATE TYPE transaction_type_enum AS ENUM('welcome_bonus','purchase','preview','video','refund','admin_adjustment');

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    amount INTEGER NOT NULL,
    type transaction_type_enum NOT NULL,
    description TEXT,
    order_id INTEGER REFERENCES orders(order_id),
    external_payment_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_external_payment_id ON transactions(external_payment_id);

-- User states table: tracks user's current interaction state
CREATE TYPE user_state_enum AS ENUM('waiting_preview_prompt','waiting_textvideo_prompt','storyboard_adding_scene','storyboard_params');

CREATE TABLE IF NOT EXISTS user_states (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    state user_state_enum NOT NULL,
    aspect_ratio TEXT,
    temp_prompt TEXT,
    temp_duration INTEGER,
    temp_quality quality_enum,
    temp_scenes JSONB,
    storyboard_total_scenes INTEGER,
    storyboard_current_scene INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_states_updated_at ON user_states(updated_at);

-- Rate limits table: anti-flood protection
CREATE TABLE IF NOT EXISTS rate_limits (
    user_id BIGINT NOT NULL,
    action_type TEXT NOT NULL,
    action_count INTEGER DEFAULT 1,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, action_type)
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start);

-- Error logs table: comprehensive error tracking
CREATE TABLE IF NOT EXISTS error_logs (
    log_id SERIAL PRIMARY KEY,
    user_id BIGINT,
    order_id INTEGER REFERENCES orders(order_id),
    workflow_name TEXT,
    error_type TEXT,
    error_message TEXT,
    telegram_update JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_error_logs_user_id ON error_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_error_logs_workflow_name ON error_logs(workflow_name);