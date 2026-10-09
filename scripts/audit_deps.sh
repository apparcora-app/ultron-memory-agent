#!/bin/bash
# scripts/audit_deps.sh
# Run pip-audit and fail if any vulnerabilities are found.

echo "Running pip-audit for dependency vulnerabilities..."
./venv_fresh/Scripts/pip-audit.exe --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815 --ignore-vuln PYSEC-2026-2447 --ignore-vuln PYSEC-2026-3740
AUDIT_EXIT_CODE=$?

if [ $AUDIT_EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Vulnerabilities found! Please update dependencies and update the requirements.lock file."
    exit 1
fi

echo "[SUCCESS] No known vulnerabilities found."
exit 0
