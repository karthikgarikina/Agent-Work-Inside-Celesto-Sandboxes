from typing import Any, Dict
from src.celesto_adapter.tool_gateway import tool_gateway, ToolExecutionResult


class AgentTools:
    """
    Computer-use tools provided to the host agent controller.
    All operations are delegated to Celesto sandboxes through the tool gateway.
    Never executes on the host.
    """

    def __init__(self, gateway=None):
        self.gateway = gateway or tool_gateway

    def run_command(self, sandbox_name: str, command: str) -> ToolExecutionResult:
        """Execute a shell command inside the Celesto sandbox."""
        return self.gateway.run_sandbox_command(sandbox_name=sandbox_name, command=command)

    def browse_web(self, sandbox_name: str, url: str) -> Dict[str, Any]:
        """Execute web browsing research inside the Celesto sandbox."""
        return self.gateway.browse_page(sandbox_name=sandbox_name, url=url)

    def write_file(self, sandbox_name: str, path: str, content: str) -> ToolExecutionResult:
        """Write a file inside the Celesto sandbox."""
        return self.gateway.write_file(sandbox_name=sandbox_name, path=path, content=content)

    def read_file(self, sandbox_name: str, path: str) -> ToolExecutionResult:
        """Read a file from inside the Celesto sandbox."""
        return self.gateway.read_file(sandbox_name=sandbox_name, path=path)


agent_tools = AgentTools()
