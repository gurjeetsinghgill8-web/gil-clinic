# ===============================================================================
# GIL CLINIC - Windows PC/Laptop ko PERMANENT server banao (Rs0, auto-restart)
#
# Clinic ka computer hi server ban jata hai - aur ye script usko aisa bana deti hai ki
# computer on hote hi app + public tunnel apne aap chalu ho jayein, aur kuch bhi
# crash ho to Windows khud restart kar de (koi "app band ho gayi" nahi).
#
# Chalane ka tarika (PowerShell **Administrator** me):
#     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-windows-service.ps1
#
#   Options:
#     -DryRun            kuch install na karo, sirf batayein kya karega
#     -Port 8000         app ka port
#     -NoTunnel          sirf LAN (clinic ke andar) - public patient link nahi
#     -Uninstall         saare tasks hata dein
#
# Ye 3 Windows Scheduled Tasks banata hai (Task Scheduler me dikhengi):
#   1) GILCLINIC-Server  -> boot par app start, crash par 1 min me restart (999 baar)
#   2) GILCLINIC-Tunnel  -> boot par Cloudflare tunnel start (public patient link)
#   3) GILCLINIC-Watchdog-> har 3 min /health check; fail ho to Server task restart
# ===============================================================================
param(
  [switch]$DryRun,
  [switch]$Uninstall,
  [switch]$NoTunnel,
  [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$LogDir = Join-Path $Root 'scratch\service-logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ServerTask = 'GILCLINIC-Server'
$TunnelTask = 'GILCLINIC-Tunnel'
$WatchdogTask = 'GILCLINIC-Watchdog'
$PythonExe = Join-Path $Root 'venv\Scripts\python.exe'
$Cloudflared = Join-Path $Root 'cloudflared.exe'

function Info($m) { Write-Host "   $m" }
function Head($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

if ($Uninstall) {
  Head 'Tasks hata rahe hain'
  foreach ($t in @($ServerTask, $TunnelTask, $WatchdogTask)) {
    if ($DryRun) { Info "[dry-run] Unregister-ScheduledTask $t" }
    else {
      try { Unregister-ScheduledTask -TaskName $t -Confirm:$false; Info "hataya: $t" }
      catch { Info "nahi mila: $t" }
    }
  }
  Write-Host "`n[OK] Uninstall poora." -ForegroundColor Green
  exit 0
}

Head '1) Check: Python + venv + cloudflared'
$VenvDir = Join-Path $Root 'venv'

# Python dhoondo (nahi hai to winget se install) - non-coder ke liye zaroori
function Find-Python {
  $cands = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
    'C:\Python312\python.exe',
    'C:\Python311\python.exe'
  )
  foreach ($c in $cands) { if (Test-Path $c) { return $c } }
  $g = Get-Command python -ErrorAction SilentlyContinue
  if ($g) { return $g.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  return $null
}

$SysPython = Find-Python
if (-not $SysPython) {
  if ($DryRun) {
    Info '[dry-run] winget install Python.Python.3.12'
    $SysPython = 'python'
  } else {
    Write-Host '   Python nahi mila - install kar raha hoon (winget se, ~1 minute)...' -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements | Out-Null
    $SysPython = Find-Python
    if (-not $SysPython) {
      Write-Host '   [ERROR] Python install nahi ho paya - python.org se install karke dobara chalayein.' -ForegroundColor Red
      exit 1
    }
  }
}
Info "python : $SysPython"

if (-not (Test-Path $PythonExe)) {
  if ($DryRun) {
    Info "[dry-run] venv banao + pip install -r requirements.txt"
  } else {
    Write-Host '   Pehli baar setup: venv bana raha hoon...' -ForegroundColor Yellow
    & $SysPython -m venv $VenvDir
    $VenvPip = Join-Path $VenvDir 'Scripts\pip.exe'
    Write-Host '   Dependencies install ho rahe hain (3-6 minute, window khuli rakhein)...' -ForegroundColor Yellow
    & $VenvPip install --upgrade pip | Out-Null
    & $VenvPip install -r (Join-Path $Root 'requirements.txt')
    if (-not (Test-Path $PythonExe)) {
      Write-Host '   [ERROR] venv nahi ban paya - is window ka output bhej dein.' -ForegroundColor Red
      exit 1
    }
  }
}
Info "venv   : $PythonExe"
$hasTunnel = Test-Path $Cloudflared
if (-not $NoTunnel -and -not $hasTunnel) {
  Write-Host "   [WARN] cloudflared.exe nahi mila -> tunnel task skip (sirf LAN chalega)." -ForegroundColor Yellow
  $NoTunnel = $true
}

Head '2) Server task (boot par start + crash par auto-restart)'
$serverArgs = "-NoProfile -WindowStyle Hidden -Command `"cd '$Root'; & '$PythonExe' -m uvicorn main_v2:app --host 0.0.0.0 --port $Port *>> '$LogDir\server.log'`""
$serverAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $serverArgs -WorkingDirectory $Root
$serverTrigger = New-ScheduledTaskTrigger -AtStartup
$serverSettings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$serverPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
  Info "[dry-run] Register $ServerTask -> uvicorn main_v2:app --port $Port (AtStartup, restart 999x/1min, SYSTEM)"
} else {
  Register-ScheduledTask -TaskName $ServerTask -Action $serverAction -Trigger $serverTrigger `
    -Settings $serverSettings -Principal $serverPrincipal -Force | Out-Null
  Start-ScheduledTask -TaskName $ServerTask
  Info "register + start: $ServerTask"
}

if (-not $NoTunnel) {
  Head '3) Tunnel task (public patient link - boot par start)'
  $tunnelArgs = "-NoProfile -WindowStyle Hidden -Command `"cd '$Root'; & '$Cloudflared' tunnel --url http://localhost:$Port --no-autoupdate *>> '$LogDir\tunnel.log'`""
  $tunnelAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $tunnelArgs -WorkingDirectory $Root
  $tunnelTrigger = New-ScheduledTaskTrigger -AtStartup
  $tunnelSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
  if ($DryRun) {
    Info "[dry-run] Register $TunnelTask -> cloudflared tunnel --url http://localhost:$Port"
  } else {
    Register-ScheduledTask -TaskName $TunnelTask -Action $tunnelAction -Trigger $tunnelTrigger `
      -Settings $tunnelSettings -Principal $serverPrincipal -Force | Out-Null
    Start-ScheduledTask -TaskName $TunnelTask
    Info "register + start: $TunnelTask"
  }
} else {
  Head '3) Tunnel skip (sirf LAN)'
  Info "Patient link sirf clinic WiFi me chalega. Ghar se access ke liye: Oracle VM (deploy/permanent/README.md)"
}

Head '4) Watchdog task (har 3 min /health check -> hang ho to restart)'
$watchdogScript = Join-Path $PSScriptRoot 'windows-watchdog.ps1'
$wdArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watchdogScript`" -Port $Port -ServerTask $ServerTask -LogDir `"$LogDir`""
$wdAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $wdArgs -WorkingDirectory $Root
$wdTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) `
  -RepetitionInterval (New-TimeSpan -Minutes 3)
$wdSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
if ($DryRun) {
  Info "[dry-run] Register $WatchdogTask -> windows-watchdog.ps1 har 3 min"
} else {
  Register-ScheduledTask -TaskName $WatchdogTask -Action $wdAction -Trigger $wdTrigger `
    -Settings $wdSettings -Principal $serverPrincipal -Force | Out-Null
  Info "register: $WatchdogTask"
}

Head '5) Firewall + power (laptop sleep na ho)'
if ($DryRun) {
  Info "[dry-run] New-NetFirewallRule port $Port (LAN)"
  Info "[dry-run] powercfg: sleep/standby never"
} else {
  try {
    if (-not (Get-NetFirewallRule -DisplayName "GIL CLINIC $Port" -ErrorAction SilentlyContinue)) {
      New-NetFirewallRule -DisplayName "GIL CLINIC $Port" -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
      Info "firewall rule: port $Port (Private profile)"
    } else { Info "firewall rule pehle se hai" }
  } catch { Info "firewall rule skip: $($_.Exception.Message)" }
  try {
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change hibernate-timeout-ac 0 | Out-Null
    powercfg /change monitor-timeout-ac 15 | Out-Null
    Info "power: sleep/hibernate OFF (AC par)"
  } catch { Info "powercfg skip" }
}

$lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " [OK] HO GAYA - clinic ka computer ab permanent server hai" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "   Doctor login (isi PC par) : http://localhost:$Port/opd/login"
if ($lanIp) { Write-Host "   Clinic ke baaki phone/PC  : http://${lanIp}:$Port/opd/login" }
if (-not $NoTunnel) {
  Write-Host "   Public patient link       : tunnel.log me URL dekhein" -ForegroundColor Yellow
  Write-Host "                               Get-Content '$LogDir\tunnel.log' | Select-String trycloudflare"
}
Write-Host ""
Write-Host "   Tasks dekhein : Get-ScheduledTask GILCLINIC-* | Format-Table TaskName,State"
Write-Host "   Band karein   : powershell -ExecutionPolicy Bypass -File deploy\permanent\install-windows-service.ps1 -Uninstall"
Write-Host ""
Write-Host "   [!]  Yaad rakhein: computer band = app band. 24/7 free ke liye Oracle VM"
Write-Host "       (deploy/permanent/README.md) - wahan ye script ki zaroorat nahi."
