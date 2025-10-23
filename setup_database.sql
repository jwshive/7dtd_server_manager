-- Database setup for 7 Days to Die server management
-- Run this as postgres superuser

-- Create database
CREATE DATABASE "7dtd";

-- Connect to the database
\c "7dtd"

-- Create tables (these will also be created automatically by the Python script)
CREATE TABLE IF NOT EXISTS player_aliases (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL UNIQUE,
    alias VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_sessions (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    login_time TIMESTAMP NOT NULL,
    logout_time TIMESTAMP,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_bundles (
    id SERIAL PRIMARY KEY,
    bundle_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bundle_items (
    id SERIAL PRIMARY KEY,
    bundle_id INTEGER NOT NULL REFERENCES item_bundles(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    quality INTEGER NOT NULL DEFAULT 1,
    UNIQUE(bundle_id, item_name)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_player_name ON player_sessions(player_name);
CREATE INDEX IF NOT EXISTS idx_login_time ON player_sessions(login_time);
CREATE INDEX IF NOT EXISTS idx_logout_time ON player_sessions(logout_time);

-- Grant permissions (optional - adjust username as needed)
-- GRANT ALL PRIVILEGES ON DATABASE "7dtd" TO your_username;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_username;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_username;
