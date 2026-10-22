import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
DEFAULT_LOG_PATH = Path("logs/commands.jsonl")


class AuditLogger:
    def __init__(self, log_path: Path = DEFAULT_LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_command(
        self,
        sandbox_name: str,
        command: str,
        decision: Literal["allow", "block"],
    ) -> dict:
        """
        Record a command attempt to logs/commands.jsonl.
        Every line strictly enforces:
          - ts: ISO-8601 string
          - sandbox_name: matches sbx-[a-z0-9]{8,}
          - command: non-empty string
          - decision: allow or block
          - execution_target: exactly 'celesto_sandbox'
        """
        if not SANDBOX_NAME_REGEX.match(sandbox_name):
            raise ValueError(
                f"Invalid sandbox_name '{sandbox_name}'. Must match sbx-[a-z0-9]{{8,}}."
            )
        if not command or not command.strip():
            raise ValueError("Command must be a non-empty string.")
        if decision not in ("allow", "block"):
            raise ValueError(f"Decision must be 'allow' or 'block', got '{decision}'.")

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sandbox_name": sandbox_name,
            "command": command.strip(),
            "decision": decision,
            "execution_target": "celesto_sandbox",
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def ensure_seeded_entry(self, sandbox_name: str = "sbx-seeddemo1"):
        """Ensure the log file exists and has at least one valid entry."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            self.log_command(
                sandbox_name=sandbox_name,
                command="echo 'Celesto Sandbox Audit Log Initialized'",
                decision="allow",
            )


audit_logger = AuditLogger()
