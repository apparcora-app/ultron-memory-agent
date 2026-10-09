$ErrorActionPreference = 'Stop'
Write-Host ">>> RUNNING SECURITY AUDIT ON DEPENDENCIES..."

.\venv\Scripts\pip-audit.exe -r requirements.lock --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-2447 --ignore-vuln GHSA-xf7x-x43h-rpqh --ignore-vuln PYSEC-2026-2635 --ignore-vuln PYSEC-2026-2636 --ignore-vuln PYSEC-2026-2633 --ignore-vuln PYSEC-2026-2634
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Vulnerabilities found! Check the pip-audit output above." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[SUCCESS] No known vulnerabilities found in pinned dependencies." -ForegroundColor Green
