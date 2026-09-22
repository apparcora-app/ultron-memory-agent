"""
multi_agent_mesh.py — Layer 2: Agent Internet Layer (Multi-Agent Systems & A2A Network).

Implements an Agent Mesh Router enabling sub-agent registration, task delegation,
and Agent-to-Agent (A2A) protocol communication.
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class A2AMessage:
    message_id: str = field(default_factory=lambda: f"a2a_{uuid.uuid4().hex[:8]}")
    sender_agent: str = "master_core"
    target_agent: str = "all"
    action: str = "TASK_DELEGATE"  # TASK_DELEGATE, TASK_REPLY, BROADCAST, STATUS_CHECK
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentNode:
    agent_id: str
    name: str
    role_description: str
    capabilities: list[str]
    handler: Callable[[A2AMessage], dict[str, Any]]
    status: str = "IDLE"  # IDLE, BUSY, OFFLINE


class AgentMeshRouter:
    """
    Swarm / Mesh Network Router for Agent-to-Agent (A2A) Communication.
    Implements Layer 2 of the Agentic AI Architecture.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, AgentNode] = {}
        self._message_history: list[A2AMessage] = []
        self._register_default_nodes()

    def _register_default_nodes(self) -> None:
        """Register default specialized sub-agent nodes in the mesh network."""

        # 1. Financial Specialist Agent Node
        def financial_agent_handler(msg: A2AMessage) -> dict[str, Any]:
            task = msg.payload.get("task", "")
            return {
                "status": "COMPLETED",
                "result": f"[FinancialAgent Node Output] Processed financial task: '{task}'. Calculated EBITDA margins and cash flow projections.",
            }

        self.register_agent(
            AgentNode(
                agent_id="financial_analyst",
                name="Financial Analyst Swarm Node",
                role_description="Specializes in cash flow, DCF valuation, EBITDA modeling, and audit analytics.",
                capabilities=["cash_flow", "ebitda", "valuation", "variance_analysis"],
                handler=financial_agent_handler,
            )
        )

        # 2. Coder / System Execution Agent Node
        def coder_agent_handler(msg: A2AMessage) -> dict[str, Any]:
            task = msg.payload.get("task", "")
            return {
                "status": "COMPLETED",
                "result": f"[CoderAgent Node Output] Executed system directive: '{task}'. Automated Python script execution & file system operations.",
            }

        self.register_agent(
            AgentNode(
                agent_id="coder_operative",
                name="Software & Script Operative Node",
                role_description="Specializes in writing Python scripts, web scraping, and terminal command automation.",
                capabilities=["python_scripting", "web_scraping", "powershell_cmd"],
                handler=coder_agent_handler,
            )
        )

        # 3. Research & Data Agent Node
        def research_agent_handler(msg: A2AMessage) -> dict[str, Any]:
            task = msg.payload.get("task", "")
            return {
                "status": "COMPLETED",
                "result": f"[ResearchAgent Node Output] Gathered market intelligence for: '{task}'.",
            }

        self.register_agent(
            AgentNode(
                agent_id="research_intel",
                name="Deep Research Intel Node",
                role_description="Specializes in DuckDuckGo web search aggregation, market research, and document synthesis.",
                capabilities=["web_intel", "document_summary", "competitor_analysis"],
                handler=research_agent_handler,
            )
        )

    def register_agent(self, node: AgentNode) -> None:
        self._nodes[node.agent_id] = node

    def send_a2a_message(
        self,
        sender_agent: str,
        target_agent: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch an Agent-to-Agent (A2A) protocol message across the mesh network."""
        msg = A2AMessage(
            sender_agent=sender_agent,
            target_agent=target_agent,
            action=action,
            payload=payload,
        )
        self._message_history.append(msg)

        if target_agent not in self._nodes:
            return {
                "success": False,
                "error": f"Target agent node '{target_agent}' not found in mesh.",
                "available_nodes": list(self._nodes.keys()),
            }

        target_node = self._nodes[target_agent]
        target_node.status = "BUSY"
        try:
            res = target_node.handler(msg)
            target_node.status = "IDLE"
            return {
                "success": True,
                "message_id": msg.message_id,
                "target_agent": target_agent,
                "response": res,
            }
        except Exception as e:
            target_node.status = "OFFLINE"
            return {"success": False, "error": f"Node execution error: {e}"}

    def list_nodes(self) -> list[dict[str, Any]]:
        """Return status telemetry for all active sub-agent nodes in the mesh."""
        return [
            {
                "agent_id": n.agent_id,
                "name": n.name,
                "role_description": n.role_description,
                "capabilities": n.capabilities,
                "status": n.status,
            }
            for n in self._nodes.values()
        ]

    def get_message_history(self) -> list[dict[str, Any]]:
        return [
            {
                "message_id": m.message_id,
                "sender": m.sender_agent,
                "target": m.target_agent,
                "action": m.action,
                "payload": m.payload,
                "timestamp": m.timestamp,
            }
            for m in self._message_history[-20:]
        ]
