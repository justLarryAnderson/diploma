CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    dataset_path TEXT,
    model_path TEXT,
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);