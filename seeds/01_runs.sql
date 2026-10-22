-- Run Ledger Database Schema

CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(64) PRIMARY KEY,
    sandbox_name VARCHAR(64) UNIQUE NOT NULL,
    problem_id VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    execution_target VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Seed row sbx-seeddemo1 with state 'deleted' and execution_target 'celesto_sandbox'
-- Idempotent: re-running does not duplicate
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at, metadata)
VALUES (
    'run-seeddemo001',
    'sbx-seeddemo1',
    'prob-research-report',
    'deleted',
    'celesto_sandbox',
    '2026-10-22T00:00:00Z',
    '2026-10-22T00:01:00Z',
    '{"seeded": true, "note": "Initial verification seed run in deleted state"}'::jsonb
)
ON CONFLICT (sandbox_name) DO UPDATE SET
    state = EXCLUDED.state,
    execution_target = EXCLUDED.execution_target,
    updated_at = EXCLUDED.updated_at;
