import re
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class RunState(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")


class RunCreate(BaseModel):
    run_id: str = Field(..., min_length=1, description="Unique run identifier")
    sandbox_name: str = Field(..., description="Unique sandbox name matching sbx-[a-z0-9]{8,}")
    problem_id: str = Field(..., min_length=1, description="Identifier of the problem or task")
    state: str = Field(..., description="Run state: created, ready, running, succeeded, failed, or deleted")
    execution_target: str = Field(..., description="Must be exactly celesto_sandbox")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not SANDBOX_NAME_REGEX.match(v):
            raise ValueError(f"Invalid sandbox_name: '{v}'. Must match sbx- followed by 8 or more lowercase letters or digits.")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        valid_states = {s.value for s in RunState}
        if v not in valid_states:
            raise ValueError(f"Invalid state: '{v}'. Must be one of {valid_states}")
        return v

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if v != "celesto_sandbox":
            raise ValueError(f"Invalid execution_target: '{v}'. Must be exactly 'celesto_sandbox'. Host execution is rejected.")
        return v


class RunResponse(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
