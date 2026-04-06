# ============================================================
#  KSTS -- Service Launcher  (Start-KSTS.ps1)
#  Shwetdhara Dairy Ticket System
#
#  Reads KSTS_HOST and KSTS_PORT from .env file.
#  Uses pipenv virtualenv path directly for reliable activation.
#
#  Usage:  powershell -ExecutionPolicy Bypass -File Start-KSTS.ps1
# ============================================================

$ProjectRoot = "C:\Users\Shwetdhara\Desktop\ticket_system_shwetdhara"
$PipfilePath = "$ProjectRoot\Pipfile"
$EnvFile     = "$ProjectRoot\.env"

function Read-EnvValue {
    param([string]$FilePath, [string]$Key)
    if (-not (Test-Path $FilePath)) { return $null }
    foreach ($line in Get-Content $FilePath) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        if ($line -match "^$Key\s*=\s*(.+)$") {
            $val = $Matches[1].Trim()
            $val = $val -replace "\s*#.*$", ""
            $val = $val.Trim('"').Trim("'")
            return $val
        }
    }
    return $null
}

function Test-PortOpen {
    param([string]$HostName, [int]$Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($HostName, $Port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

Clear-Host
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "   ##  ##     #####   #########   #####  " -ForegroundColor Green
Write-Host "   ## ##     ##          ##      ##      " -ForegroundColor Green
Write-Host "   ####       ####       ##       ####   " -ForegroundColor Green
Write-Host "   ## ##         ##      ##          ##  " -ForegroundColor Green
Write-Host "   ##  ##    #####       ##      #####   " -ForegroundColor Green
Write-Host ""
Write-Host "   Shwetdhara Dairy  --  Ticket System" -ForegroundColor Yellow
Write-Host "   Service Launcher  v3.0  (pipenv)"    -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Yellow
Write-Host ""

# ------------------------------------------------------------
#  READ .ENV
# ------------------------------------------------------------
Write-Host "  Reading .env ..." -ForegroundColor Magenta

if (-not (Test-Path $EnvFile)) {
    Write-Host "  [x] .env not found at: $EnvFile" -ForegroundColor Red
    Read-Host "`n  Press Enter to exit"
    exit 1
}

$SERVER_HOST = Read-EnvValue $EnvFile "KSTS_HOST"
$SERVER_PORT = Read-EnvValue $EnvFile "KSTS_PORT"
if (-not $SERVER_HOST) { $SERVER_HOST = "127.0.0.1" }
if (-not $SERVER_PORT) { $SERVER_PORT = "8000" }
$BIND_ADDR = "${SERVER_HOST}:${SERVER_PORT}"

Write-Host "  [+] Server  : $BIND_ADDR"   -ForegroundColor Green
Write-Host "  [+] Project : $ProjectRoot" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
#  PRE-FLIGHT CHECKS
# ------------------------------------------------------------
Write-Host "  Running pre-flight checks ..." -ForegroundColor Magenta

if (-not (Test-Path "$ProjectRoot\manage.py")) {
    Write-Host "  [x] manage.py not found" -ForegroundColor Red
    Read-Host "`n  Press Enter to exit"; exit 1
}
Write-Host "  [+] manage.py found" -ForegroundColor Green

if (-not (Test-Path $PipfilePath)) {
    Write-Host "  [x] Pipfile not found in $ProjectRoot" -ForegroundColor Red
    Read-Host "`n  Press Enter to exit"; exit 1
}
Write-Host "  [+] Pipfile found" -ForegroundColor Green

if (-not (Get-Command pipenv -ErrorAction SilentlyContinue)) {
    Write-Host "  [x] pipenv not found on PATH" -ForegroundColor Red
    Read-Host "`n  Press Enter to exit"; exit 1
}
Write-Host "  [+] pipenv found" -ForegroundColor Green

# ------------------------------------------------------------
#  RESOLVE VENV PATH FROM PIPENV
# ------------------------------------------------------------
Write-Host "  Resolving virtualenv path ..." -ForegroundColor Magenta

$env:PIPENV_PIPFILE = $PipfilePath
$VenvPath = (& pipenv --venv 2>$null).Trim()

if (-not $VenvPath -or -not (Test-Path $VenvPath)) {
    Write-Host "  [x] Could not resolve pipenv virtualenv path." -ForegroundColor Red
    Write-Host "      Run:  pipenv install  inside your project folder." -ForegroundColor Yellow
    Read-Host "`n  Press Enter to exit"; exit 1
}

$PythonExe = "$VenvPath\Scripts\python.exe"
$CeleryExe = "$VenvPath\Scripts\celery.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "  [x] python.exe not found at: $PythonExe" -ForegroundColor Red
    Read-Host "`n  Press Enter to exit"; exit 1
}

if (-not (Test-Path $CeleryExe)) {
    Write-Host "  [x] celery.exe not found at: $CeleryExe" -ForegroundColor Red
    Write-Host "      Run:  pipenv install celery django-celery-beat redis" -ForegroundColor Yellow
    Read-Host "`n  Press Enter to exit"; exit 1
}

Write-Host "  [+] Virtualenv : $VenvPath" -ForegroundColor Green
Write-Host "  [+] Python     : $PythonExe" -ForegroundColor Green
Write-Host "  [+] Celery     : $CeleryExe" -ForegroundColor Green

if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
    Write-Host "  [x] Windows Terminal (wt.exe) not found" -ForegroundColor Red
    Write-Host "      Install it free from the Microsoft Store." -ForegroundColor Yellow
    Read-Host "`n  Press Enter to exit"; exit 1
}
Write-Host "  [+] Windows Terminal found" -ForegroundColor Green

if (Test-PortOpen "127.0.0.1" 6379) {
    Write-Host "  [+] Redis reachable on localhost:6379" -ForegroundColor Green
} else {
    Write-Host "  [!] Redis NOT detected on localhost:6379 -- start Redis before Celery" -ForegroundColor Yellow
    Write-Host "      Download Redis from: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Yellow
}

if (Test-PortOpen $SERVER_HOST ([int]$SERVER_PORT)) {
    Write-Host "  [!] Port $BIND_ADDR already in use -- Django may already be running" -ForegroundColor Yellow
} else {
    Write-Host "  [+] Port $BIND_ADDR is free" -ForegroundColor Green
}

Write-Host ""

# ------------------------------------------------------------
#  BUILD TERMINAL TAB COMMANDS
#  Use direct paths to executables instead of activate.bat
# ------------------------------------------------------------

# Tab 1: Django Server (using direct python path)
$tab1 = "new-tab --title `"KSTS  Django  [$BIND_ADDR]`" cmd /k `"cd /d $ProjectRoot && $PythonExe manage.py runserver $BIND_ADDR`""

# Tab 2: Celery Worker (using direct celery path)
$tab2 = "new-tab --title `"KSTS  Celery Worker`" cmd /k `"cd /d $ProjectRoot && $CeleryExe -A ticket_system worker --loglevel=info --pool=solo`""

# Tab 3: Celery Beat (using direct celery path)
$tab3 = "new-tab --title `"KSTS  Celery Beat`" cmd /k `"cd /d $ProjectRoot && $CeleryExe -A ticket_system beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler`""

$wtArgs = "$tab1 ; $tab2 ; $tab3"

# ------------------------------------------------------------
#  LAUNCH
# ------------------------------------------------------------
Write-Host "  Starting services in Windows Terminal ..." -ForegroundColor Magenta
Write-Host ""
Write-Host "    Tab 1  -->  Django Dev Server  [$BIND_ADDR]" -ForegroundColor Green
Write-Host "    Tab 2  -->  Celery Worker  (pool=solo)"      -ForegroundColor Cyan
Write-Host "    Tab 3  -->  Celery Beat  (DatabaseScheduler)" -ForegroundColor Magenta
Write-Host ""

# Kill any existing wt.exe processes to avoid conflicts
Get-Process wt.exe -ErrorAction SilentlyContinue | Stop-Process -Force

# Start new Windows Terminal with all tabs
Start-Process wt.exe -ArgumentList $wtArgs

Start-Sleep -Seconds 3

Write-Host "  ================================================================" -ForegroundColor Yellow
Write-Host "  [OK]  All 3 services launched!" -ForegroundColor Green
Write-Host ""
Write-Host "        Django  -->  http://$BIND_ADDR"       -ForegroundColor White
Write-Host "        Worker  -->  watch Tab 2 in terminal" -ForegroundColor Cyan
Write-Host "        Beat    -->  watch Tab 3 in terminal" -ForegroundColor Magenta
Write-Host ""
Write-Host "  To change server: edit .env  -->  KSTS_HOST / KSTS_PORT" -ForegroundColor DarkGray
Write-Host "  ================================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  IMPORTANT: Make sure Redis is running before Celery starts!" -ForegroundColor Yellow
Write-Host "  If Celery fails, install dependencies with: pipenv install" -ForegroundColor Yellow
Write-Host ""

Read-Host "  Press Enter to close this launcher"