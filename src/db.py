import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    text,
)
from sqlalchemy.types import JSON
from src.config import settings

logger = logging.getLogger(__name__)

metadata = MetaData()

# Define runs table schema
runs_table = Table(
    "runs",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("sandbox_name", String(64), unique=True, nullable=False),
    Column("problem_id", String(64), nullable=False),
    Column("state", String(32), nullable=False),
    Column("execution_target", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)),
    Column("metadata", JSON, default=dict),
)


class DatabaseManager:
    def __init__(self, db_url: Optional[str] = None):
        raw_url = db_url or settings.database_url
        if raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
            raw_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        self.db_url = raw_url
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self.db_url,
                    pool_pre_ping=True,
                    pool_recycle=300,
                )
            except Exception as e:
                logger.warning(f"Failed to create database engine: {e}")
                raise
        return self._engine

    def check_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.debug(f"DB connection check failed: {e}")
            return False

    def init_db(self):
        try:
            metadata.create_all(self.engine)
            self.seed_default_run()
        except Exception as e:
            logger.warning(f"init_db encountered error: {e}")

    def seed_default_run(self):
        query = text("""
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
        """)
        try:
            with self.engine.begin() as conn:
                conn.execute(query)
        except Exception as e:
            logger.warning(f"Failed to execute seed query: {e}")

    def get_runs(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            stmt = select(runs_table).order_by(runs_table.c.created_at.asc())
            result = conn.execute(stmt)
            rows = []
            for row in result.mappings():
                r = dict(row)
                if isinstance(r.get("created_at"), datetime):
                    r["created_at"] = r["created_at"].isoformat()
                if isinstance(r.get("updated_at"), datetime):
                    r["updated_at"] = r["updated_at"].isoformat()
                rows.append(r)
            return rows

    def create_or_update_run(
        self,
        run_id: str,
        sandbox_name: str,
        problem_id: str,
        state: str,
        execution_target: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        meta_data = meta or {}

        query = text("""
            INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at, metadata)
            VALUES (:run_id, :sandbox_name, :problem_id, :state, :execution_target, :now, :now, :meta)
            ON CONFLICT (sandbox_name) DO UPDATE SET
                run_id = EXCLUDED.run_id,
                problem_id = EXCLUDED.problem_id,
                state = EXCLUDED.state,
                execution_target = EXCLUDED.execution_target,
                updated_at = EXCLUDED.updated_at,
                metadata = EXCLUDED.metadata
            RETURNING run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at, metadata;
        """)

        with self.engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "run_id": run_id,
                    "sandbox_name": sandbox_name,
                    "problem_id": problem_id,
                    "state": state,
                    "execution_target": execution_target,
                    "now": now,
                    "meta": json.dumps(meta_data),
                },
            )
            row = result.mappings().first()
            if row:
                r = dict(row)
                if isinstance(r.get("created_at"), datetime):
                    r["created_at"] = r["created_at"].isoformat()
                if isinstance(r.get("updated_at"), datetime):
                    r["updated_at"] = r["updated_at"].isoformat()
                return r
            return {
                "run_id": run_id,
                "sandbox_name": sandbox_name,
                "problem_id": problem_id,
                "state": state,
                "execution_target": execution_target,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "metadata": meta_data,
            }


db_manager = DatabaseManager()
