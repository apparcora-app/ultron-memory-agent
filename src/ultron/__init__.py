"""
ultron — Enterprise-grade autonomous AI cognitive system with persistent long-term memory.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import sys


class _UltronAliasLoader:
    def __init__(self, target_name: str):
        self.target_name = target_name

    def create_module(self, spec):
        mod = importlib.import_module(self.target_name)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class _UltronAliasFinder:
    FLAT_MODULE_MAP = {
        "config": "ultron.core.config",
        "contracts": "ultron.core.contracts",
        "model_router": "ultron.core.model_router",
        "tool_definitions": "ultron.core.tool_definitions",
        "tool_router": "ultron.core.tool_router",
        "profiles": "ultron.core.profiles",
        "llm_gateway": "ultron.core.llm_gateway",
        "file_processor": "ultron.infrastructure.file_processor",
        "sandbox": "ultron.infrastructure.sandbox",
        "mcp_client": "ultron.infrastructure.mcp_client",
        "mcp_stdio_bridge": "ultron.infrastructure.mcp_stdio_bridge",
        "desktop_action_verifier": "ultron.infrastructure.desktop_action_verifier",
        "email_engine": "ultron.infrastructure.email_engine",
        "read_pdf": "ultron.infrastructure.read_pdf",
        "backend_service": "ultron.infrastructure.backend_service",
        "chat_session_manager": "ultron.memory.chat_session_manager",
        "core_memory": "ultron.memory.core_memory",
        "memory_manager": "ultron.memory.memory_manager",
        "trajectory_manager": "ultron.memory.trajectory_manager",
        "qdrant_store": "ultron.memory.qdrant_store",
        "embeddings": "ultron.memory.embeddings",
        "skill_manager": "ultron.skills.skill_manager",
        "skill_evolution": "ultron.skills.skill_evolution",
        "skill_mutation_engine": "ultron.skills.skill_mutation_engine",
        "ledger_service": "ultron.accounting_modules.ledger_service",
        "app": "ultron.cli.web",
        "main": "ultron.cli.main",
        "crewai_pipeline": "ultron.pipelines.crewai_pipeline",
        "langchain_pipeline": "ultron.pipelines.langchain_pipeline",
        "langgraph_pipeline": "ultron.pipelines.langgraph_pipeline",
        "swarm_orchestrator": "ultron.pipelines.swarm_orchestrator",
        "multi_agent_mesh": "ultron.pipelines.multi_agent_mesh",
        "killswitch": "ultron.security.killswitch",
        "environment": "ultron.security.environment",
        "pii_cleanup": "ultron.security.pii_cleanup",
        "pii_redaction": "ultron.security.pii_redaction",
        "tot_engine": "ultron.reasoning.tot_engine",
        "dreaming_core": "ultron.reasoning.dreaming_core",
        "dreaming_engine": "ultron.reasoning.dreaming_engine",
        "reflection_engine": "ultron.reasoning.reflection_engine",
        "graph_rag_engine": "ultron.reasoning.graph_rag_engine",
        "hierarchical_planner": "ultron.reasoning.hierarchical_planner",
        "prompt_optimizer": "ultron.reasoning.prompt_optimizer",
        "expel_trajectory_bank": "ultron.reasoning.expel_trajectory_bank",
    }
    PACKAGES = (
        "core", "memory", "reasoning", "security", "governance", "pipelines",
        "rag", "infrastructure", "guardrails", "subsystems", "concurrency",
        "telemetry", "tax_modules", "accounting_modules", "skills", "interfaces",
        "utils", "execution", "streaming", "agent", "rules", "anti_fabrication_gate",
        "resilience"
    )

    def find_spec(self, fullname: str, path, target=None):
        parts = fullname.split(".")
        prefix = parts[0]
        sub = ("." + ".".join(parts[1:])) if len(parts) > 1 else ""
        if prefix in self.FLAT_MODULE_MAP:
            target_name = self.FLAT_MODULE_MAP[prefix] + sub
        elif prefix in self.PACKAGES:
            target_name = "ultron." + fullname
        else:
            return None

        try:
            mod = importlib.import_module(target_name)
            is_pkg = hasattr(mod, "__path__")
        except Exception:
            is_pkg = False
        return importlib.machinery.ModuleSpec(
            fullname,
            _UltronAliasLoader(target_name),
            is_package=is_pkg,
        )


if not any(isinstance(f, _UltronAliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _UltronAliasFinder())

__version__ = "1.3.0"

# Main cognitive agent entrypoint
from ultron.agent import MemoryAgent

__all__ = [
    "MemoryAgent",
    "__version__",
]
