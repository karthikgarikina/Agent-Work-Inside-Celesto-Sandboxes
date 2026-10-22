import time
from typing import Any, Dict, Optional
from pydantic import BaseModel
from src.celesto_adapter.audit_logger import audit_logger
from src.celesto_adapter.safety_policy import CommandBlockedError, safety_policy


class ToolExecutionResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    command: str
    sandbox_name: str
    blocked: bool = False
    error_message: Optional[str] = None


class ToolGateway:
    """
    Explicit tool boundary between host agent controller and Celesto sandbox.
    Every command and tool request is audited, evaluated against safety policies,
    and executed strictly inside the Celesto sandbox.
    """

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from src.celesto_adapter.client import celesto_client
            self._client = celesto_client
        return self._client

    def run_sandbox_command(
        self,
        sandbox_name: str,
        command: str,
    ) -> ToolExecutionResult:
        """
        Execute a shell command inside the named Celesto sandbox.
        Appends to logs/commands.jsonl. If blocked, logs block and raises CommandBlockedError.
        Never executes on the host.
        """
        start_time = time.time()

        # Step 1: Safety check
        try:
            safety_policy.evaluate(command=command, sandbox_name=sandbox_name)
        except CommandBlockedError as e:
            # Log blocked command with execution_target: celesto_sandbox
            audit_logger.log_command(
                sandbox_name=sandbox_name,
                command=command,
                decision="block",
            )
            duration = time.time() - start_time
            return ToolExecutionResult(
                success=False,
                exit_code=126,
                stdout="",
                stderr=f"CommandBlockedError: {e.message}",
                duration_s=duration,
                command=command,
                sandbox_name=sandbox_name,
                blocked=True,
                error_message=e.message,
            )

        # Step 2: Log allowed command
        audit_logger.log_command(
            sandbox_name=sandbox_name,
            command=command,
            decision="allow",
        )

        # Step 3: Execute in sandbox via Celesto client
        try:
            result = self.client.exec_in_sandbox(sandbox_name=sandbox_name, command=command)
            duration = time.time() - start_time
            return ToolExecutionResult(
                success=(result.get("exit_code", 0) == 0),
                exit_code=result.get("exit_code", 0),
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                duration_s=duration,
                command=command,
                sandbox_name=sandbox_name,
                blocked=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            return ToolExecutionResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_s=duration,
                command=command,
                sandbox_name=sandbox_name,
                blocked=False,
                error_message=str(e),
            )

    def write_file(self, sandbox_name: str, path: str, content: str) -> ToolExecutionResult:
        """Write file inside Celesto sandbox."""
        cmd = f"cat << 'EOF' > {path}\n{content}\nEOF"
        return self.run_sandbox_command(sandbox_name=sandbox_name, command=cmd)

    def read_file(self, sandbox_name: str, path: str) -> ToolExecutionResult:
        """Read file from inside Celesto sandbox."""
        cmd = f"cat {path}"
        return self.run_sandbox_command(sandbox_name=sandbox_name, command=cmd)

    def browse_page(self, sandbox_name: str, url: str) -> Dict[str, Any]:
        """
        Execute sandboxed browser research inside the Celesto guest.
        Extracts content without exposing host.
        """
        # Run curl or python scraper inside the guest computer
        cmd = f"curl -sL --max-time 15 '{url}' | head -n 100"
        res = self.run_sandbox_command(sandbox_name=sandbox_name, command=cmd)
        return {
            "url": url,
            "success": res.success,
            "content": res.stdout,
            "error": res.stderr if not res.success else None,
        }


tool_gateway = ToolGateway()
