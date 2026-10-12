"""
security package — Multi-Tenant Sandbox Isolation, Context Scrubbing & Threat Defenses.

Exports:
  1. Tenant Isolation & Workspace Sandboxing:
     - SecurityContext, get_current_security_context, security_context
     - IsolatedVectorStore, default_isolated_vector_store, TenantAccessViolationError
     - TenantWorkspaceSandbox, default_tenant_sandbox, DirectoryTraversalError
  2. PII & Secret Redaction:
     - DataSanitizer, default_sanitizer, sanitize_text, sanitize_payload
"""

from ultron.security.sanitizer import (
    DataSanitizer,
    default_sanitizer,
    sanitize_payload,
    sanitize_text,
)
from ultron.security.tenant_isolation import (
    DirectoryTraversalError,
    IsolatedVectorStore,
    SecurityContext,
    TenantAccessViolationError,
    TenantWorkspaceSandbox,
    default_isolated_vector_store,
    default_tenant_sandbox,
    get_current_security_context,
    security_context,
)

__all__ = [
    # Security Context & Isolation
    "SecurityContext",
    "get_current_security_context",
    "security_context",
    "IsolatedVectorStore",
    "default_isolated_vector_store",
    "TenantAccessViolationError",
    "TenantWorkspaceSandbox",
    "default_tenant_sandbox",
    "DirectoryTraversalError",
    # Sanitizer
    "DataSanitizer",
    "default_sanitizer",
    "sanitize_text",
    "sanitize_payload",
]
