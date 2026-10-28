"""
ultron.core.pipeline — Modular Cognitive Pipeline for Ultron Memory Agent.
"""

from ultron.core.pipeline.context import PipelineContext
from ultron.core.pipeline.dispatcher import CognitivePipeline
from ultron.core.pipeline.stages.context_stage import ContextStage
from ultron.core.pipeline.stages.execution_stage import ExecutionStage
from ultron.core.pipeline.stages.verification_stage import VerificationStage

__all__ = [
    "CognitivePipeline",
    "PipelineContext",
    "ContextStage",
    "ExecutionStage",
    "VerificationStage",
]
