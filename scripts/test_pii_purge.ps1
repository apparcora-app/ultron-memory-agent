$ErrorActionPreference = "Stop"
cd "e:\Personal Data\Apps\AI Agents\ultron-memory-agent"

$env:ULTRON_DATA_DIR = Join-Path $env:TEMP "ultron_pii_test"
if (Test-Path $env:ULTRON_DATA_DIR) {
    Remove-Item -Recurse -Force $env:ULTRON_DATA_DIR
}
New-Item -ItemType Directory -Force -Path $env:ULTRON_DATA_DIR | Out-Null

Write-Host ">>> SETTING UP FAKE DATA in $env:ULTRON_DATA_DIR..."
python scripts/setup_pii_test.py

Write-Host "`n>>> RUNNING PII PURGE (DRY-RUN)..."
python pii_cleanup.py --dry-run

Write-Host "`n>>> VERIFYING FILES STILL EXIST AFTER DRY-RUN..."
if (Test-Path "$env:ULTRON_DATA_DIR/sessions/old_sess.json") { Write-Host "old_sess.json exists" } else { Write-Host "old_sess.json missing!" ; exit 1 }
if (Test-Path "$env:ULTRON_DATA_DIR/blackboard/old_bb.json") { Write-Host "old_bb.json exists" } else { Write-Host "old_bb.json missing!" ; exit 1 }

Write-Host "`n>>> RUNNING PII PURGE (LIVE)..."
python pii_cleanup.py

Write-Host "`n>>> VERIFYING OLD RECORDS ARE GONE AND NEW RECORDS REMAIN..."
if (-not (Test-Path "$env:ULTRON_DATA_DIR/sessions/old_sess.json")) { Write-Host "old_sess.json successfully purged." } else { Write-Host "old_sess.json NOT purged!" ; exit 1 }
if (Test-Path "$env:ULTRON_DATA_DIR/sessions/new_sess.json") { Write-Host "new_sess.json safely retained." } else { Write-Host "new_sess.json incorrectly purged!" ; exit 1 }

if (-not (Test-Path "$env:ULTRON_DATA_DIR/blackboard/old_bb.json")) { Write-Host "old_bb.json successfully purged." } else { Write-Host "old_bb.json NOT purged!" ; exit 1 }
if (Test-Path "$env:ULTRON_DATA_DIR/blackboard/new_bb.json") { Write-Host "new_bb.json safely retained." } else { Write-Host "new_bb.json incorrectly purged!" ; exit 1 }

# Check DB
python scripts/verify_telemetry.py
Write-Host "`n>>> PII RETENTION LIFECYCLE TEST COMPLETED SUCCESSFULLY."
