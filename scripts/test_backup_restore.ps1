$ErrorActionPreference = "Stop"
cd "e:\Personal Data\Apps\AI Agents\ultron-memory-agent"

Write-Host ">>> RUNNING BACKUP..."
python scripts/backup.py

Write-Host "`n>>> VERIFYING BACKUP FILE EXISTS..."
$backupFile = Get-ChildItem -Path "mock_remote" -Filter "*.enc" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $backupFile) {
    Write-Host "No backup file found!"
    exit 1
}
Write-Host "Found backup: $($backupFile.Name)"

Write-Host "`n>>> TAMPERING WITH ORIGINAL DATA (Deleting config.py and telemetry.db)..."
Copy-Item "config.py" "config.py.bak" -Force
Copy-Item "data/telemetry.db" "data/telemetry.db.bak" -Force

Remove-Item "config.py" -Force
Remove-Item "data/telemetry.db" -Force

if (-not (Test-Path "config.py")) { Write-Host "config.py successfully deleted." }
if (-not (Test-Path "data/telemetry.db")) { Write-Host "data/telemetry.db successfully deleted." }

Write-Host "`n>>> RUNNING RESTORE..."
python scripts/restore.py "mock_remote\$($backupFile.Name)"

Write-Host "`n>>> DIFFING RESTORED FILES AGAINST ORIGINALS (using file hashes)..."
$configHash1 = (Get-FileHash "config.py").Hash
$configHash2 = (Get-FileHash "config.py.bak").Hash

$telemetryHash1 = (Get-FileHash "data/telemetry.db").Hash
$telemetryHash2 = (Get-FileHash "data/telemetry.db.bak").Hash

if ($configHash1 -eq $configHash2 -and $telemetryHash1 -eq $telemetryHash2) {
    Write-Host "[SUCCESS] DIFF PASSED: Restored files match originals exactly."
} else {
    Write-Host "[ERROR] DIFF FAILED: Restored files do not match!"
    exit 1
}

# Cleanup
Remove-Item "config.py.bak" -Force
Remove-Item "data/telemetry.db.bak" -Force
Write-Host "`n>>> BACKUP & RESTORE LIFECYCLE TEST COMPLETED SUCCESSFULLY."
