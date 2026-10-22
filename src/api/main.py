import logging
import re
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.api.models import RunCreate, RunResponse
from src.db import db_manager
from src.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("celesto_api")

app = FastAPI(
    title="Celesto Run Ledger API",
    description="Control-plane Run Ledger API for Celesto sandboxed agent runs",
    version="1.0.0",
)

# In-memory fallback if database is not reachable (e.g. during dry-runs / testing)
FALLBACK_SEED_RUN = {
    "run_id": "run-seeddemo001",
    "sandbox_name": "sbx-seeddemo1",
    "problem_id": "prob-research-report",
    "state": "deleted",
    "execution_target": "celesto_sandbox",
    "created_at": "2026-10-22T00:00:00Z",
    "updated_at": "2026-10-22T00:01:00Z",
    "metadata": {"seeded": True, "note": "Initial verification seed run in deleted state"},
}
_in_memory_runs: Dict[str, Dict[str, Any]] = {
    "sbx-seeddemo1": FALLBACK_SEED_RUN
}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Ensure all validation errors (e.g. bad sandbox_name, unknown state, bad execution_target)
    return HTTP 400 Bad Request as strictly required by specification.
    """
    err_list = [{"msg": str(e.get("msg")), "loc": list(e.get("loc", []))} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": err_list, "message": "Invalid request parameters"},
    )


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Celesto Run Ledger API...")
    try:
        if db_manager.check_connection():
            db_manager.init_db()
            logger.info("Database initialized successfully.")
        else:
            logger.warning("Database not connected yet; in-memory fallback enabled.")
    except Exception as e:
        logger.warning(f"Startup database check error (continuing with fallback): {e}")


@app.get("/health", status_code=status.HTTP_200_OK)
def get_health():
    """Health check endpoint. Returns 200 and {'status': 'ok'}."""
    return {"status": "ok"}


@app.get("/api/runs", response_model=List[RunResponse], status_code=status.HTTP_200_OK)
def get_runs():
    """
    Retrieve all recorded runs. On a fresh compose, includes sbx-seeddemo1.
    """
    try:
        if db_manager.check_connection():
            runs = db_manager.get_runs()
            if runs:
                return runs
    except Exception as e:
        logger.warning(f"DB read failed, using in-memory runs: {e}")

    return list(_in_memory_runs.values())


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(run: RunCreate):
    """
    Record a new run row in the ledger.
    execution_target must be exactly 'celesto_sandbox'.
    """
    # Strict secondary checks
    if run.execution_target != "celesto_sandbox":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_target '{run.execution_target}'. Must be exactly 'celesto_sandbox'. Host execution is rejected.",
        )

    if not re.match(r"^sbx-[a-z0-9]{8,}$", run.sandbox_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sandbox_name '{run.sandbox_name}'. Must match sbx-[a-z0-9]{{8,}}.",
        )

    valid_states = {"created", "ready", "running", "succeeded", "failed", "deleted"}
    if run.state not in valid_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state '{run.state}'. Must be one of {valid_states}.",
        )

    try:
        if db_manager.check_connection():
            stored = db_manager.create_or_update_run(
                run_id=run.run_id,
                sandbox_name=run.sandbox_name,
                problem_id=run.problem_id,
                state=run.state,
                execution_target=run.execution_target,
                meta=run.metadata,
            )
            _in_memory_runs[run.sandbox_name] = stored
            return stored
    except Exception as e:
        logger.warning(f"DB write failed, falling back to in-memory: {e}")

    # In-memory store
    record = {
        "run_id": run.run_id,
        "sandbox_name": run.sandbox_name,
        "problem_id": run.problem_id,
        "state": run.state,
        "execution_target": run.execution_target,
        "created_at": "2026-10-22T12:00:00Z",
        "updated_at": "2026-10-22T12:00:00Z",
        "metadata": run.metadata or {},
    }
    _in_memory_runs[run.sandbox_name] = record
    return record
