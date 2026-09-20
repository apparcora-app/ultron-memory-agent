"""
security/tenant_isolation.py — Multi-Tenant Memory & Workspace Isolation.

Provides:
  1. Immutable SecurityContext: frozen (tenant_id, user_id, session_id).
  2. Context-propagated security tokens via contextvars.
  3. Non-bypassable driver-level vector store isolation with forced metadata filtering.
  4. Filesystem & artifact sandboxing with realpath canonicalization blocking directory traversal (../)
     and symlink escapes.
"""

from __future__ import annotations

import contextvars
import os
import shutil
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── 1. Security Context & Propagation ────────────────────────────────────────

class SecurityContext(BaseModel):
    """
    Immutable security context representing the authenticated boundary of an execution turn.
    Guaranteed frozen: cannot be mutated by model inferences, tool hooks, or payload injections.
    """
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    tenant_id: str = Field(..., min_length=1, description="Globally unique tenant / organization identifier")
    user_id: str = Field(..., min_length=1, description="Authenticated user identifier")
    session_id: str = Field(..., min_length=1, description="Unique conversation / task session identifier")


_current_security_context: contextvars.ContextVar[Optional[SecurityContext]] = contextvars.ContextVar(
    "current_security_context", default=None
)


def get_current_security_context() -> Optional[SecurityContext]:
    """Returns the currently active SecurityContext in the current async execution context."""
    return _current_security_context.get()


@contextmanager
def security_context(ctx: SecurityContext) -> Iterator[SecurityContext]:
    """Context manager binding a SecurityContext to the current execution thread/task."""
    token = _current_security_context.set(ctx)
    try:
        yield ctx
    finally:
        _current_security_context.reset(token)


# ── 2. Vector Store & Memory Driver Isolation ─────────────────────────────────

class TenantAccessViolationError(PermissionError):
    """Raised when an operation attempts unauthorized cross-tenant data access."""
    pass


class IsolatedVectorStore:
    """
    Driver-level multi-tenant vector memory wrapper.
    Enforces non-bypassable tenant isolation at the data access layer, outside model or prompt control.
    """

    def __init__(self) -> None:
        # In-memory document collection: id -> {text, embedding_dim, metadata}
        self._records: Dict[str, Dict[str, Any]] = {}

    def insert(
        self,
        record_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[SecurityContext] = None,
    ) -> Dict[str, Any]:
        """
        Inserts a memory item, forcefully stamping immutable tenant_id and user_id metadata.
        """
        active_ctx = ctx or get_current_security_context()
        if not active_ctx:
            raise TenantAccessViolationError("Cannot insert vector memory without an active SecurityContext.")

        meta = dict(metadata or {})
        # Force non-bypassable driver-level metadata stamping
        meta["tenant_id"] = active_ctx.tenant_id
        meta["user_id"] = active_ctx.user_id
        meta["session_id"] = active_ctx.session_id

        doc = {
            "id": record_id,
            "text": text,
            "metadata": meta,
        }
        self._records[record_id] = doc
        return doc

    def query(
        self,
        query_text: str,
        metadata_filter: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        ctx: Optional[SecurityContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Queries vector memory with mandatory driver-level tenant isolation filtering.
        Even if the model or caller supplies an empty filter, the tenant_id filter is injected.
        """
        active_ctx = ctx or get_current_security_context()
        if not active_ctx:
            raise TenantAccessViolationError("Cannot query vector memory without an active SecurityContext.")

        # Injected non-bypassable driver filter: {"tenant_id": {"$eq": active_ctx.tenant_id}}
        forced_tenant_id = active_ctx.tenant_id

        # Scan and enforce strict tenant matching
        matching: List[Dict[str, Any]] = []
        for record in self._records.values():
            rec_meta = record.get("metadata", {})
            # Hard boundary check: record tenant_id must strictly match active context tenant_id
            if rec_meta.get("tenant_id") == forced_tenant_id:
                # Basic text matching or semantic score simulation
                if query_text.lower() in record["text"].lower() or query_text == "*":
                    matching.append(record)

        return matching[:limit]

    def count_for_tenant(self, tenant_id: str) -> int:
        return sum(1 for r in self._records.values() if r.get("metadata", {}).get("tenant_id") == tenant_id)

    def clear(self) -> None:
        self._records.clear()


# Global default isolated memory store
default_isolated_vector_store = IsolatedVectorStore()


# ── 3. Filesystem & Artifact Sandboxing ────────────────────────────────────────

class DirectoryTraversalError(PermissionError):
    """Raised when a file operation attempts to escape the tenant sandbox boundaries."""
    pass


class TenantWorkspaceSandbox:
    """
    Sandboxes all dynamic file reads, writes, and scratchpads into dedicated per-tenant paths.
    Strictly prevents directory traversal (../, absolute paths, symlink attacks) outside
    the tenant's root scratchpad.
    """

    def __init__(self, base_artifacts_dir: str = "./artifacts") -> None:
        self.base_artifacts_dir = os.path.realpath(os.path.abspath(base_artifacts_dir))
        os.makedirs(self.base_artifacts_dir, exist_ok=True)

    def get_tenant_root(self, ctx: Optional[SecurityContext] = None) -> str:
        """Computes and ensures the canonical root directory for the tenant and session."""
        active_ctx = ctx or get_current_security_context()
        if not active_ctx:
            raise TenantAccessViolationError("Cannot access tenant workspace without an active SecurityContext.")

        tenant_dir = os.path.realpath(os.path.join(self.base_artifacts_dir, active_ctx.tenant_id, active_ctx.session_id))
        os.makedirs(tenant_dir, exist_ok=True)
        return tenant_dir

    def resolve_safe_path(self, relative_path: str, ctx: Optional[SecurityContext] = None) -> str:
        """
        Resolves a user-provided relative path against the tenant sandbox root.
        Enforces canonicalization via os.path.realpath and checks path boundaries.
        """
        sandbox_root = self.get_tenant_root(ctx)

        # Normalize and construct candidate path
        candidate_path = os.path.normpath(os.path.join(sandbox_root, relative_path))
        canonical_path = os.path.realpath(candidate_path)

        # Prefix boundary assertion
        # Adding separator ensures /root/tenant1 doesn't match /root/tenant10
        root_prefix = sandbox_root if sandbox_root.endswith(os.sep) else sandbox_root + os.sep

        if canonical_path != sandbox_root and not canonical_path.startswith(root_prefix):
            raise DirectoryTraversalError(
                f"Directory traversal attack detected: target '{relative_path}' "
                f"resolved to '{canonical_path}' outside sandbox boundary '{sandbox_root}'."
            )

        return canonical_path

    def safe_write(
        self,
        relative_path: str,
        content: str | bytes,
        ctx: Optional[SecurityContext] = None,
    ) -> str:
        """Safely writes content within the tenant's sandbox."""
        resolved_path = self.resolve_safe_path(relative_path, ctx)
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

        if isinstance(content, str):
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(resolved_path, "wb") as f:
                f.write(content)

        return resolved_path

    def safe_read(
        self,
        relative_path: str,
        as_bytes: bool = False,
        ctx: Optional[SecurityContext] = None,
    ) -> str | bytes:
        """Safely reads content from within the tenant's sandbox."""
        resolved_path = self.resolve_safe_path(relative_path, ctx)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"File '{relative_path}' not found in tenant sandbox.")

        if as_bytes:
            with open(resolved_path, "rb") as f:
                return f.read()
        else:
            with open(resolved_path, "r", encoding="utf-8") as f:
                return f.read()

    def list_files(self, ctx: Optional[SecurityContext] = None) -> List[str]:
        """Lists all files present in the current tenant session sandbox."""
        root = self.get_tenant_root(ctx)
        files: List[str] = []
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                full_p = os.path.join(dirpath, filename)
                rel_p = os.path.relpath(full_p, root)
                files.append(rel_p)
        return files

    def clean_session(self, ctx: Optional[SecurityContext] = None) -> None:
        """Removes all files in the current tenant session sandbox."""
        root = self.get_tenant_root(ctx)
        if os.path.exists(root):
            shutil.rmtree(root)


# Global default tenant workspace sandbox
default_tenant_sandbox = TenantWorkspaceSandbox()
