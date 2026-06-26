-- Создание таблицы для email
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы для телефонов
CREATE TABLE IF NOT EXISTS phones (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание пользователя для бота
CREATE USER task_bot_user WITH PASSWORD 'task_bot_password';
GRANT SELECT, INSERT ON emails, phones TO task_bot_user;
GRANT USAGE ON SEQUENCE emails_id_seq, phones_id_seq TO task_bot_user;

-- Создание базы данных
CREATE DATABASE task_bot;
GRANT ALL PRIVILEGES ON DATABASE task_bot TO task_bot_user;
