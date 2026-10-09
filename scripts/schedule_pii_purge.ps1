# schedule_pii_purge.ps1
# This script sets up a Windows Task Scheduler job to run the PII cleanup script daily.

$taskName = "UltronPrime_PII_Purge"
$scriptPath = Resolve-Path ".\pii_cleanup.py"
$pythonPath = (Resolve-Path ".\venv_fresh\Scripts\python.exe").Path
$workingDir = (Get-Item .).FullName

Write-Host "Creating Scheduled Task: $taskName"
Write-Host "Python Path: $pythonPath"
Write-Host "Script Path: $scriptPath"

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $workingDir
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

# Run whether user is logged on or not
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
    Write-Host "[SUCCESS] Windows Scheduled Task '$taskName' registered successfully."
    Write-Host "It will run daily at 3:00 AM."
} catch {
    Write-Host "[ERROR] Failed to create Scheduled Task. Try running PowerShell as Administrator."
    Write-Host $_.Exception.Message
}
