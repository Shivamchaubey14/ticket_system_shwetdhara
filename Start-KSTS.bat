@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0Start-KSTS.ps1"

# Setup-KSTS.ps1 - Run this once to configure easy launching

$ProjectPath = "C:\Users\Shwetdhara\Desktop\ticket_system_shwetdhara"
$ScriptPath = "$ProjectPath\Start-KSTS.ps1"

# Create batch file for easy launching
$BatchContent = @"
@echo off
cd /d $ProjectPath
powershell -ExecutionPolicy Bypass -File "$ScriptPath"
"@

$BatchContent | Out-File -FilePath "$ProjectPath\Start-KSTS.bat" -Encoding ascii
Write-Host "✓ Created Start-KSTS.bat" -ForegroundColor Green

# Add to PowerShell profile if not already there
if (-not (Test-Path $PROFILE)) {
    New-Item -Path $PROFILE -Type File -Force | Out-Null
}

$ProfileContent = Get-Content $PROFILE -ErrorAction SilentlyContinue
if ($ProfileContent -notmatch "Start-KSTS") {
    Add-Content -Path $PROFILE -Value "`n# Alias for KSTS Service Launcher"
    Add-Content -Path $PROFILE -Value "function Start-KSTS { & '$ScriptPath' }"
    Add-Content -Path $PROFILE -Value "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force"
    Write-Host "✓ Added function to PowerShell profile" -ForegroundColor Green
}

Write-Host ""
Write-Host "Setup complete! You can now launch KSTS using:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Method 1: Type 'Start-KSTS' in PowerShell" -ForegroundColor Cyan
Write-Host "  Method 2: Type 'Start-KSTS.bat' in Command Prompt" -ForegroundColor Cyan
Write-Host "  Method 3: Double-click Start-KSTS.bat in File Explorer" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Enter to reload your profile and test..."
Read-Host

# Reload profile
. $PROFILE

# Test it
Write-Host ""
Write-Host "Testing: Type 'Start-KSTS' now to launch your services!" -ForegroundColor Green