"""
subsystems/execution.py — Execution & Action Subsystem for Ultron Protocol.

Encapsulates all physical and agentic execution layers:
- Sandbox (resource limits, timeout, directory traversal protection)
- ToolExecutor (ULTRON_TOOLS dispatcher)
- MCPManager (Model Context Protocol client bridge)
- AgentMeshRouter (A2A protocol network & mesh routing)
- SwarmOrchestrator (multi-agent squad orchestration)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from config import ToolConfig
from mcp_client import MCPManager
from multi_agent_mesh import AgentMeshRouter
from sandbox import Sandbox, SandboxConfig
from swarm_orchestrator import SwarmOrchestrator
from tool_definitions import ToolExecutor


@dataclass
class ExecutionSubsystem:
    """Cohesive facade managing tool execution, sandboxing, MCP integration, mesh, and swarm."""
    sandbox: Sandbox
    tool_executor: ToolExecutor
    mcp: MCPManager
    mesh: AgentMeshRouter
    swarm: SwarmOrchestrator

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool through the guarded tool executor."""
        return self.tool_executor.execute(name, args)

    @classmethod
    def create_default(
        cls,
        tool_cfg: Optional[ToolConfig] = None,
        skills: Any = None,
        telemetry: Any = None,
    ) -> ExecutionSubsystem:
        """Factory creating the production-grade execution subsystem."""
        tool_cfg = tool_cfg or ToolConfig()

        sandbox = Sandbox(SandboxConfig(
            max_tool_iterations=tool_cfg.max_iterations,
            command_timeout=tool_cfg.command_timeout,
            python_timeout=tool_cfg.python_timeout,
            max_output_length=tool_cfg.max_output_length,
        ))

        tool_executor = ToolExecutor(sandbox=sandbox)
        mcp = MCPManager()
        mesh = AgentMeshRouter()
        swarm = SwarmOrchestrator(skill_manager=skills, telemetry=telemetry)

        return cls(
            sandbox=sandbox,
            tool_executor=tool_executor,
            mcp=mcp,
            mesh=mesh,
            swarm=swarm,
        )
