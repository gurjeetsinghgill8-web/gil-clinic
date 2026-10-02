# ==============================================================================
#  GIL CLINIC - PERMANENT PUBLIC URL (bina card, bina kharcha)
#
#  Aapke PC par app chalti hai; ye script usko internet par ek PERMANENT
#  https:// address de deti hai - taaki patient ghar se link khol sake.
#
#  3 raste (sab me card NAHI lagta):
#    -Provider tailscale   (RECOMMENDED) permanent address, har restart par same
#                          https://<naam>.<tailnet>.ts.net  - sirf ek baar Google/email login
#    -Provider ngrok        1 free static domain (account free, no card)
#    -Provider cloudflare   koi account hi nahi (par address har restart par badalta hai;
#                          script .env khud update kar deti hai)
#
#  Chalane ka tarika (PowerShell Administrator):
#     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-permanent-url.ps1
#     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-permanent-url.ps1 -Provider ngrok
#     powershell -ExecutionPolicy Bypass -File deploy\permanent\install-permanent-url.ps1 -Status
#
#  -DryRun  -> kuch install nahi karega, sirf batayega kya karega
# ==============================================================================
param(
  [ValidateSet('tailscale', 'ngrok', 'cloudflare')]
  [string]$Provider = 'tailscale',
  [int]$Port = 8000,
  [switch]$DryRun,
  [switch]$Status
)

$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$EnvFile = Join-Path $Root '.env'
$ServerTask = 'GILCLINIC-Server'
$TunnelTask = 'GILCLINIC-Tunnel'
$Repo = 'https://github.com/gurjeetsinghgill8-web/gil-clinic.git'

function Head($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Info($m) { Write-Host "   $m" }
function Ok($m) { Write-Host "   [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "   [!] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "   [X] $m" -ForegroundColor Red }

function Test-Tool($name, $path = '') {
  if ($path -and (Test-Path $path)) { return $path }
  $c = Get-Command $name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return $null
}

function Set-EnvBaseUrl([string]$url) {
  if (-not (Test-Path $EnvFile)) {
    Warn ".env nahi mila ($EnvFile) - pehle START_LOCAL.bat chalayein"
    return $false
  }
  $lines = Get-Content $EnvFile -Encoding UTF8
  $found = $false
  $out = foreach ($l in $lines) {
    if ($l -match '^\s*APP_BASE_URL=') { $found = $true; "APP_BASE_URL=$url" } else { $l }
  }
  if (-not $found) { $out = @($out) + "APP_BASE_URL=$url" }
  if ($DryRun) { Info "[dry-run] .env me likhta: APP_BASE_URL=$url"; return $true }
  # BOM ke bina save (python-dotenv ke liye saaf)
  [System.IO.File]::WriteAllLines($EnvFile, [string[]]$out, (New-Object System.Text.UTF8Encoding($false)))
  Ok ".env update: APP_BASE_URL=$url"
  return $true
}

function Restart-App {
  $t = Get-ScheduledTask -TaskName $ServerTask -ErrorAction SilentlyContinue
  if ($t) {
    if ($DryRun) { Info "[dry-run] restart task $ServerTask" ; return }
    Stop-ScheduledTask -TaskName $ServerTask -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $ServerTask
    Ok "app restart ($ServerTask) - naya URL ab patient links me jayega"
  } else {
    Warn "app task nahi mila ($ServerTask). App ko ek baar band karke dobara START_LOCAL.bat se chalayein."
  }
}

function Register-TunnelTask([string]$exe, [string]$args, [string]$name = $TunnelTask) {
  $action = New-ScheduledTaskAction -Execute $exe -Argument $args -WorkingDirectory $Root
  $trigger = New-ScheduledTaskTrigger -AtStartup
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
  $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
  if ($DryRun) {
    Info "[dry-run] task register: $name -> $exe $args"
    return
  }
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
  Start-ScheduledTask -TaskName $name
  Ok "auto-start task ban gaya: $name (boot par khud chalu)"
}

function Show-Status {
  Head 'Status'
  $ts = Test-Tool 'tailscale' 'C:\Program Files\Tailscale\tailscale.exe'
  Info ("tailscale : " + ($(if ($ts) { $ts } else { 'install nahi' })))
  $ng = Test-Tool 'ngrok'
  Info ("ngrok     : " + ($(if ($ng) { $ng } else { 'install nahi' })))
  $cf = Test-Path (Join-Path $Root 'cloudflared.exe')
  Info ("cloudflared: " + ($(if ($cf) { 'mil gaya' } else { 'nahi mila' })))
  if (Test-Path $EnvFile) {
    $line = (Get-Content $EnvFile -Encoding UTF8 | Where-Object { $_ -match '^APP_BASE_URL=' } | Select-Object -First 1)
    Info ("APP_BASE_URL: " + ($(if ($line) { $line } else { 'set nahi' })))
  }
  foreach ($t in @($ServerTask, $TunnelTask, "$TunnelTask-Ngrok", "$TunnelTask-Tailscale")) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($task) { Info ("task {0,-26} : {1}" -f $t, $task.State) }
  }
  Head 'DONE - ye screen copy karke bhej dein agar madad chahiye'
}

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "   GIL CLINIC - PERMANENT PUBLIC URL (bina card)" -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Info "Provider: $Provider   Port: $Port   DryRun: $([bool]$DryRun)"

if ($Status) { Show-Status; exit 0 }

#  App chalu hai? 
Head '0) App check'
$healthOk = $false
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 8 -UseBasicParsing
  if ($r.StatusCode -eq 200) { $healthOk = $true }
} catch { $healthOk = $false }
if ($healthOk) { Ok "app chal rahi hai (http://127.0.0.1:$Port/health OK)" }
else { Warn "app abhi jawab nahi de rahi - pehle START_LOCAL.bat chalayein (tunnel phir bhi set ho jayega)" }

$publicUrl = ''

switch ($Provider) {

  #  TAILSCALE FUNNEL
  'tailscale' {
    Head '1) Tailscale install/check'
    $ts = Test-Tool 'tailscale' 'C:\Program Files\Tailscale\tailscale.exe'
    if (-not $ts) {
      if ($DryRun) { Info "[dry-run] winget install Tailscale.Tailscale" }
      else {
        Info "Tailscale install kar raha hoon (winget se, free, no card)..."
        winget install --id Tailscale.Tailscale -e --accept-package-agreements --accept-source-agreements | Out-Null
        $ts = Test-Tool 'tailscale' 'C:\Program Files\Tailscale\tailscale.exe'
      }
    }
    if ($ts) { Ok "tailscale: $ts" } else { Warn "tailscale abhi install nahi hua (winget fail?)" }

    Head '2) Login (ek baar - Google/email, koi card nahi)'
    if ($ts -and -not $DryRun) {
      $st = & $ts status --json 2>$null | ConvertFrom-Json
      if ($st -and $st.Self -and $st.Self.DNSName) {
        Ok "pehle se logged in: $($st.Self.DNSName)"
      } else {
        Info "Browser khulega - apne Google/email se login karein (FREE plan, card nahi maangta)"
        Info "Login ke baad ye window khud aage badh jayegi..."
        Start-Process $ts -ArgumentList 'up' -Wait
      }
    } else { Info "[dry-run] tailscale up (login)" }

    Head '3) Funnel chalu (permanent public HTTPS)'
    if ($ts -and -not $DryRun) {
      # Funnel ko ek baar admin console me allow karna pad sakta hai - CLI link deta hai
      $funnelOut = & $ts funnel --bg $Port 2>&1 | Out-String
      Info $funnelOut.Trim()
      if ($funnelOut -match 'https://login\.tailscale\.com|enable') {
        Warn "Tailscale ne Funnel enable karne ka link diya hai - usko browser me khol kar allow karein,"
        Warn "phir ye script dobara chalayein (bas ek baar ka kaam hai)."
      }
      $st = & $ts status --json 2>$null | ConvertFrom-Json
      if ($st -and $st.Self -and $st.Self.DNSName) {
        $dns = ($st.Self.DNSName -replace '\.$', '')
        $publicUrl = "https://$dns"
        Ok "permanent address: $publicUrl"
      }
    } else { Info "[dry-run] tailscale funnel --bg $Port" }

    if (-not $DryRun -and $ts) {
      Register-TunnelTask 'powershell.exe' "-NoProfile -WindowStyle Hidden -Command `"& '$ts' funnel --bg $Port`"" "$TunnelTask-Tailscale"
    }
  }

  #  NGROK
  'ngrok' {
    Head '1) ngrok install/check'
    $ng = Test-Tool 'ngrok'
    if (-not $ng) {
      if ($DryRun) { Info "[dry-run] winget install Ngrok.Ngrok" }
      else {
        Info "ngrok install kar raha hoon (winget se, free account, no card)..."
        winget install --id Ngrok.Ngrok -e --accept-package-agreements --accept-source-agreements | Out-Null
        $ng = Test-Tool 'ngrok'
      }
    }
    if ($ng) { Ok "ngrok: $ng" } else { Warn "ngrok install nahi hua" }

    Head '2) ngrok account (free, card nahi) + authtoken'
    Info "1. https://dashboard.ngrok.com/signup par free account banayein (Google se, card nahi)"
    Info "2. Dashboard -> Your Authtoken -> copy"
    Info "3. Yahan paste karein:"
    $token = Read-Host "   ngrok authtoken"
    if ($ng -and $token -and -not $DryRun) {
      & $ng config add-authtoken $token | Out-Null
      Ok "authtoken save ho gaya"
    }
    Info "4. Dashboard -> Domains -> apna FREE static domain copy karein (jaise: gilclinic.ngrok-free.app)"
    $domain = Read-Host "   ngrok static domain"
    if ($ng -and $domain -and -not $DryRun) {
      $publicUrl = "https://$domain"
      Register-TunnelTask $ng "http --url=$publicUrl $Port" "$TunnelTask-Ngrok"
    } elseif ($DryRun) {
      Info "[dry-run] ngrok http --url=https://<domain> $Port"
    }
  }

  #  CLOUDFLARE (no signup)
  'cloudflare' {
    Head '1) Cloudflare quick tunnel (koi account nahi)'
    $cf = Test-Path (Join-Path $Root 'cloudflared.exe')
    if (-not $cf) {
      Fail "cloudflared.exe repo me nahi mila. Ise download karke repo folder me rakhein:"
      Info "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
      exit 1
    }
    Ok "cloudflared.exe mil gaya"
    Info "Is raste me address har restart par badalta hai - script .env khud update karti hai,"
    Info "lekin patient ko bheja purana link kaam nahi karega. Isliye tailscale better hai."
    $py = Test-Path (Join-Path $Root 'venv\Scripts\python.exe')
    $pyExe = if ($py) { Join-Path $Root 'venv\Scripts\python.exe' } else { 'python' }
    Register-TunnelTask $pyExe "`"$Root\start_tunnel.py`"" "$TunnelTask-Cloudflare"
    if (-not $DryRun) { Warn "cloudflare mode me APP_BASE_URL tunnel khud set karta hai (start_tunnel.py se)" }
  }
}

#  .env + app restart 
Head '4) App ko naya address batana'
if ($publicUrl) {
  if (Set-EnvBaseUrl $publicUrl) { Restart-App }
} else {
  Warn "address abhi nahi mila - upar ke steps poore karke script dobara chalayein"
}

Head 'DONE'
if ($publicUrl) {
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "   AAPKA PERMANENT ADDRESS (patient ko yahi bhejein)" -ForegroundColor Green
  Write-Host "     $publicUrl" -ForegroundColor Green
  Write-Host "     Doctor login: $publicUrl/opd/login   (PIN 5554)" -ForegroundColor Green
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host ""
  Info "Test: is address ko PHONE me khol kar dekhein (WiFi band karke bhi - ghar se bhi khulega)"
} else {
  Warn "address upar ke output me dekhein, ya -Status se check karein"
}
Info "Status dekhne ke liye: powershell -ExecutionPolicy Bypass -File deploy\permanent\install-permanent-url.ps1 -Status"
