<#
.SYNOPSIS
    Ultron Emergency Kill-Switch & Process Terminator.
.DESCRIPTION
    Instantly engages emergency lockdown and terminates all active Ultron processes.
#>

Write-Host "======================================================================" -ForegroundColor Red
Write-Host " 🚨 [EMERGENCY KILL-SWITCH] ENGAGING ULTRON LOCKDOWN" -ForegroundColor Red
Write-Host "======================================================================" -ForegroundColor Yellow

Set-Location "$PSScriptRoot\.."
python killswitch.py

Write-Host "`n[✓] All Ultron services have been killed. Lockdown file written." -ForegroundColor Green
