"""
tests/test_phase6_security.py — Test Suite for Phase 6 Multi-Tenant Sandbox & Sanitization.

Validates:
  1. Immutable SecurityContext & context propagation.
  2. Strict vector store driver-level tenant isolation (zero cross-tenant memory leakage).
  3. Filesystem sandbox & directory traversal protection (os.path.realpath canonicalization).
  4. Boundary PII & secret redaction (SSN, EIN, credit cards, API keys, Bearer tokens, JWTs).
  5. Recursive payload sanitization & automatic DLQ redaction.
"""

import os
import tempfile
import pytest
from pydantic import ValidationError

from resilience.dlq import DeadLetterQueue
from security.sanitizer import (
    DataSanitizer,
    default_sanitizer,
    sanitize_payload,
    sanitize_text,
)
from security.tenant_isolation import (
    DirectoryTraversalError,
    IsolatedVectorStore,
    SecurityContext,
    TenantAccessViolationError,
    TenantWorkspaceSandbox,
    get_current_security_context,
    security_context,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── 1. Security Context Immutability & Contextvars Propagation ────────────────

def test_security_context_immutability():
    ctx = SecurityContext(tenant_id="tenant_alpha", user_id="user_1", session_id="sess_100")

    assert ctx.tenant_id == "tenant_alpha"
    assert ctx.user_id == "user_1"
    assert ctx.session_id == "sess_100"

    # Strict immutability check
    with pytest.raises(ValidationError):
        ctx.tenant_id = "tenant_beta"  # type: ignore

    # Prohibit extra injected fields
    with pytest.raises(ValidationError):
        SecurityContext(tenant_id="t", user_id="u", session_id="s", injected_admin=True)  # type: ignore


def test_security_context_propagation():
    assert get_current_security_context() is None

    ctx = SecurityContext(tenant_id="org_77", user_id="u_99", session_id="s_11")
    with security_context(ctx):
        current = get_current_security_context()
        assert current is not None
        assert current.tenant_id == "org_77"
        assert current.session_id == "s_11"

    # Must reset after context exit
    assert get_current_security_context() is None


# ── 2. Vector Store Multi-Tenant Memory Isolation ─────────────────────────────

def test_vector_store_driver_level_tenant_isolation():
    store = IsolatedVectorStore()

    ctx_a = SecurityContext(tenant_id="tenant_A", user_id="alice", session_id="sess_A")
    ctx_b = SecurityContext(tenant_id="tenant_B", user_id="bob", session_id="sess_B")

    # Insert Tenant A memories
    with security_context(ctx_a):
        store.insert("rec_a1", "Tenant A quarterly earnings: $5M revenue")
        store.insert("rec_a2", "Tenant A internal payroll spreadsheet details")

    # Insert Tenant B memories
    with security_context(ctx_b):
        store.insert("rec_b1", "Tenant B secret merger proposal with Acme")
        store.insert("rec_b2", "Tenant B revenue metrics: $10M revenue")

    assert store.count_for_tenant("tenant_A") == 2
    assert store.count_for_tenant("tenant_B") == 2

    # Query as Tenant A: searching for "merger" (belonging to Tenant B) MUST return 0
    with security_context(ctx_a):
        results_a = store.query("merger")
        assert len(results_a) == 0

        # Searching for "revenue" (shared term) MUST return ONLY Tenant A's record
        results_rev_a = store.query("revenue")
        assert len(results_rev_a) == 1
        assert results_rev_a[0]["id"] == "rec_a1"
        assert results_rev_a[0]["metadata"]["tenant_id"] == "tenant_A"

    # Query as Tenant B: searching for "payroll" (belonging to Tenant A) MUST return 0
    with security_context(ctx_b):
        results_b = store.query("payroll")
        assert len(results_b) == 0

        # Searching for "revenue" MUST return ONLY Tenant B's record
        results_rev_b = store.query("revenue")
        assert len(results_rev_b) == 1
        assert results_rev_b[0]["id"] == "rec_b2"
        assert results_rev_b[0]["metadata"]["tenant_id"] == "tenant_B"

    # Query without SecurityContext must raise TenantAccessViolationError
    with pytest.raises(TenantAccessViolationError):
        store.query("revenue")


# ── 3. Filesystem Sandboxing & Directory Traversal Defense ────────────────────

def test_tenant_workspace_sandbox_and_traversal_defense():
    with tempfile.TemporaryDirectory() as tmp_artifacts:
        sandbox = TenantWorkspaceSandbox(base_artifacts_dir=tmp_artifacts)
        ctx = SecurityContext(tenant_id="tenant_omega", user_id="user_root", session_id="session_42")

        with security_context(ctx):
            # Happy path: write and read within tenant session sandbox
            written_path = sandbox.safe_write("reports/summary.txt", "Tenant Omega Confidential Report")
            assert os.path.exists(written_path)

            content = sandbox.safe_read("reports/summary.txt")
            assert content == "Tenant Omega Confidential Report"

            files = sandbox.list_files()
            assert any("summary.txt" in f for f in files)

            # Attack Vector 1: Directory traversal via parent directory ../
            with pytest.raises(DirectoryTraversalError):
                sandbox.resolve_safe_path("../../passwords.txt")

            with pytest.raises(DirectoryTraversalError):
                sandbox.safe_write("../../../evil.sh", "echo hacked")

            # Attack Vector 2: Traversal to other tenant's folder
            with pytest.raises(DirectoryTraversalError):
                sandbox.safe_read("../other_tenant/session/data.json")

            # Attack Vector 3: Absolute system path escape
            if os.name == "nt":
                with pytest.raises(DirectoryTraversalError):
                    sandbox.resolve_safe_path("C:\\Windows\\System32\\calc.exe")
            else:
                with pytest.raises(DirectoryTraversalError):
                    sandbox.resolve_safe_path("/etc/shadow")


# ── 4. Boundary PII & Secret Redaction ────────────────────────────────────────

def test_pii_and_secret_redaction_patterns():
    sanitizer = DataSanitizer()

    # 1. US SSN / ITIN
    text_ssn = "Customer SSN is 123-45-6789 and spouse ITIN is 987-65-4321."
    clean_ssn = sanitizer.sanitize_text(text_ssn)
    assert "123-45-6789" not in clean_ssn
    assert "987-65-4321" not in clean_ssn
    assert clean_ssn == "Customer SSN is [REDACTED_SSN] and spouse ITIN is [REDACTED_SSN]."

    # 2. Employer Identification Number (EIN)
    text_ein = "Corporate EIN is 12-3456789 for tax filing."
    clean_ein = sanitizer.sanitize_text(text_ein)
    assert "12-3456789" not in clean_ein
    assert clean_ein == "Corporate EIN is [REDACTED_EIN] for tax filing."

    # 3. Credit Card Numbers
    text_cc = "Charged card 4111-2222-3333-4444 for $150.00."
    clean_cc = sanitizer.sanitize_text(text_cc)
    assert "4111-2222-3333-4444" not in clean_cc
    assert "[REDACTED_CC]" in clean_cc

    # 4. API Keys & Auth Tokens
    text_keys = (
        "Anthropic key sk-ant-api03-abcdef12345678901234, "
        "OpenAI key sk-proj12345678901234567890, "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signature12345, "
        "api_key: 'supersecrettoken1234567890'"
    )
    clean_keys = sanitizer.sanitize_text(text_keys)
    assert "sk-ant-" not in clean_keys
    assert "sk-proj" not in clean_keys
    assert "supersecrettoken" not in clean_keys
    assert "[REDACTED_TOKEN]" in clean_keys


def test_recursive_payload_sanitization():
    payload = {
        "user": {
            "name": "John Doe",
            "ssn": "999-11-2222",
            "ein": "88-1234567",
        },
        "credentials": [
            {"provider": "anthropic", "key": "sk-ant-live-token-123456789"},
            {"provider": "openai", "token": "sk-test-live-token-98765432101"},
        ],
        "metadata": ("safe_tuple_item", "Credit card: 4111-2222-3333-4444"),
    }

    sanitized = sanitize_payload(payload)

    assert sanitized["user"]["ssn"] == "[REDACTED_SSN]"
    assert sanitized["user"]["ein"] == "[REDACTED_EIN]"
    assert sanitized["credentials"][0]["key"] == "[REDACTED_TOKEN]"
    assert sanitized["credentials"][1]["token"] == "[REDACTED_TOKEN]"
    assert sanitized["metadata"][1] == "Credit card: [REDACTED_CC]"


def test_dlq_automatic_sanitization_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "dlq_sanitized.db")
        dlq = DeadLetterQueue(db_path=db_path)

        # Emit an error with sensitive API key and SSN
        record = dlq.record_dead_letter(
            failed_service="external_payment_api",
            node_name="payment_processor",
            error_message="Unauthorized call with token sk-ant-secret123456789 for user with SSN 123-45-6789",
            input_payload={"account_ein": "12-3456789", "card": "4111-2222-3333-4444"},
        )

        persisted = dlq.get_dead_letter(record.dlq_id)
        assert persisted is not None

        # Assert no sensitive data was saved into SQLite
        assert "sk-ant-secret" not in persisted.error_message
        assert "123-45-6789" not in persisted.error_message
        assert "[REDACTED_TOKEN]" in persisted.error_message
        assert "[REDACTED_SSN]" in persisted.error_message

        # Assert input payload was sanitized
        assert "12-3456789" not in str(persisted.input_payload)
        assert "4111-2222-3333-4444" not in str(persisted.input_payload)
        assert "[REDACTED_EIN]" in str(persisted.input_payload)
        assert "[REDACTED_CC]" in str(persisted.input_payload)
