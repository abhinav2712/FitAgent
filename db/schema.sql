-- FitAgent schema v2 — multi-user, plans versioned, agent fully audited.
-- Every data row belongs to a user; user scoping is injected by Python code
-- (token → user_id), NEVER chosen by the LLM.

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    api_token       TEXT NOT NULL UNIQUE, -- bearer credential: tracker app + iPhone Shortcut (X-Api-Token)
    telegram_chat_id TEXT,                -- per-user DM target; the bot token is global
    tz              TEXT DEFAULT 'Asia/Kolkata',   -- informational for now; cron runs in the worker tz
    lat             NUMERIC(9,6),         -- for Swiggy search when the real MCP lands
    lng             NUMERIC(9,6),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE health_metrics (
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    steps           INTEGER,
    active_kcal     INTEGER,
    workouts        JSONB DEFAULT '[]',   -- [{type, distance_km, duration_min, avg_pace_min_per_km}]
    raw_payload     JSONB,
    received_at     TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, date)
);

CREATE TABLE meal_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    meal_id         TEXT NOT NULL,        -- 'b','l','s','d','x' or 'offplan:<n>'
    name            TEXT NOT NULL,
    kcal            INTEGER NOT NULL,
    protein_g       INTEGER NOT NULL,
    checked         BOOLEAN DEFAULT true,
    source          TEXT DEFAULT 'app',   -- app | agent_comment
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, date, meal_id)
);

CREATE TABLE weight_logs (
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    weight_kg       NUMERIC(5,2) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, date)
);

CREATE TABLE comments (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    text            TEXT NOT NULL,
    processed       BOOLEAN DEFAULT false,
    agent_run_id    INTEGER,              -- set by worker after processing; GET /log/chat joins this for the in-app reply
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Plans are append-only. Active plan = a user's latest row with approved = true.
CREATE TABLE plan_versions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    plan            JSONB NOT NULL,       -- full plan document (targets, meals by weekday, workouts)
    patch           JSONB,                -- RFC6902 patch vs previous version (null for seed)
    rationale       TEXT,
    source          TEXT NOT NULL,        -- seed | agent | user
    approved        BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_runs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    trigger         TEXT NOT NULL,        -- nightly | comment | swiggy_window
    input_context   JSONB,
    tool_calls      JSONB DEFAULT '[]',
    output_text     TEXT,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE recommendations (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    items           JSONB NOT NULL,       -- [{restaurant, dish, est_kcal, est_protein, price, reason}]
    remaining_kcal  INTEGER,
    remaining_protein INTEGER,
    agent_run_id    INTEGER REFERENCES agent_runs(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE pending_approvals (
    id              SERIAL PRIMARY KEY,
    plan_version_id INTEGER REFERENCES plan_versions(id),  -- owner = plan_versions.user_id
    summary         TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_meal_logs_user_date ON meal_logs(user_id, date);
CREATE INDEX idx_comments_unprocessed ON comments(processed) WHERE processed = false;
CREATE INDEX idx_plan_versions_user ON plan_versions(user_id, id DESC) WHERE approved = true;
