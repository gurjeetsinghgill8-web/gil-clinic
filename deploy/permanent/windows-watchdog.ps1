# ═══════════════════════════════════════════════════════════════════════════════
# GIL CLINIC - Windows watchdog (har 3 min /health check)
#
# install-windows-service.ps1 isko scheduled task ke roop me register karta hai.
# App HANG ho jaye (crash na ho, bas jawab na de) to bhi server task restart ho jata hai.
# ═══════════════════════════════════════════════════════════════════════════════
param(
  [int]$Port = 8000,
  [string]$ServerTask = 'GILCLINIC-Server',
  [string]$LogDir = ''
)

$ErrorActionPreference = 'SilentlyContinue'
if (-not $LogDir) { $LogDir = Join-Path $env:TEMP 'gilclinic-logs' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir 'watchdog.log'

function Write-Log($msg) {
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
  Add-Content -Path $LogFile -Value $line
}

$url = "http://127.0.0.1:$Port/health"
$alive = $false
for ($i = 1; $i -le 3; $i++) {
  try {
    $r = Invoke-WebRequest -Uri $url -TimeoutSec 8 -UseBasicParsing
    if ($r.StatusCode -eq 200 -and $r.Content -match '"ok"') { $alive = $true; break }
  } catch { }
  Start-Sleep -Seconds 5
}

if ($alive) {
  exit 0
}

Write-Log "/health fail (3 koshish) - $ServerTask restart kar raha hoon"
Stop-ScheduledTask -TaskName $ServerTask
Start-Sleep -Seconds 3
Start-ScheduledTask -TaskName $ServerTask
Write-Log "$ServerTask restart bhej diya"
