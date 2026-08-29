# deploy_remote.ps1 — GIL CLINIC one-command deploy (Windows laptop se Oracle/Google VM par)
#
# Oracle VM banne ke baad, is laptop par bas ye chalao:
#   .\deploy_remote.ps1 -VmIp 123.45.67.89 -KeyPath .\gil-clinic-key.key
#
# Ye script khud:
#   1. SSH connection test karta hai
#   2. deploy_oracle.sh ko VM par upload karke chala deta hai (sudo)
#   3. VM ke public URL par health check karta hai (2 min tak wait)
#   4. VM ke admin credentials wapas laptop par le aata hai
#   5. Data backup pull karne ka option deta hai
#
# Pehle se chahiye: VM chalu (Ubuntu 22.04), port 22 + 8000 open,
# SSH private key is laptop par saved.
param(
    [Parameter(Mandatory = $true)]
    [string]$VmIp,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [ValidateSet("Deploy", "PullBackup")]
    [string]$Mode = "Deploy",

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"
$sshBase = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes")
$target = "${User}@${VmIp}"

function Run-Ssh([string]$command) {
    & ssh @sshBase $target $command
    if ($LASTEXITCODE -ne 0) { throw "SSH command fail hui: $command" }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GIL CLINIC — VM Deploy Helper" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VM:   ${VmIp}"
Write-Host "  User: ${User}"
Write-Host "  Key:  ${KeyPath}"
Write-Host ""

if (-not (Test-Path $KeyPath)) { throw "SSH key nahi mili: $KeyPath" }

if ($Mode -eq "PullBackup") {
    Write-Host "==> [Backup pull] VM se latest backup laptop par le aate hain..."
    New-Item -ItemType Directory -Force -Path ".\vm_backups" | Out-Null
    $latest = & ssh @sshBase $target "ls -t /opt/gilclinic/data/backups/*.db 2>/dev/null | head -1"
    if (-not $latest) { throw "VM par koi backup nahi mila (ya /opt/gilclinic/data/backups khali hai)" }
    $latest = $latest.Trim()
    Write-Host "   Latest backup: $latest"
    & scp @sshBase "${target}:${latest}" ".\vm_backups\"
    if ($LASTEXITCODE -ne 0) { throw "scp fail" }
    Write-Host "   [OK] Backup aa gaya: .\vm_backups\" -ForegroundColor Green
    exit 0
}

# ── Step 1: SSH test ────────────────────────────────────────────────
Write-Host "==> [1/5] SSH test..."
Run-Ssh "echo VM_OK; uname -a"

# ── Step 2: Upload + run deploy script ─────────────────────────────
Write-Host "==> [2/5] deploy_oracle.sh VM par upload..."
& scp @sshBase ".\deploy_oracle.sh" "${target}:~/"
if ($LASTEXITCODE -ne 0) { throw "scp fail" }
Write-Host "   [OK] Uploaded"

Write-Host "==> [3/5] VM par deploy chal raha hai (5-10 min lag sakte hain)..."
Run-Ssh "sudo bash ~/deploy_oracle.sh"

# ── Step 4: Health check (public IP par) ───────────────────────────
Write-Host "==> [4/5] Health check: http://${VmIp}:8000/health"
$ok = $false
for ($i = 0; $i -lt 24; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://${VmIp}:8000/health" -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200 -and $r.Content -match '"ok"') {
            $ok = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $ok) { throw "Health check FAIL — Oracle console mein port 8000 open karein (Security List), phir dobara try karein" }
Write-Host "   [OK] App LIVE: http://${VmIp}:8000" -ForegroundColor Green

# ── Step 5: Admin credentials wapas le aao ─────────────────────────
Write-Host "==> [5/5] Admin credentials VM se laptop par..."
New-Item -ItemType Directory -Force -Path ".\vm_credentials" | Out-Null
& scp @sshBase "${target}:/opt/gilclinic/admin_credentials.txt" ".\vm_credentials\"
if ($LASTEXITCODE -ne 0) {
    Write-Host "   [WARN] credentials file nahi mili (VM console se dekh lein)"
} else {
    Write-Host "   [OK] Saved: .\vm_credentials\admin_credentials.txt" -ForegroundColor Green
}

Write-Host ""
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DEPLOY COMPLETE!"
Write-Host "  Website: http://${VmIp}:8000"
Write-Host ""
Write-Host "  Abhi karna hai (ek baar):"
Write-Host "   [1] Oracle console → Security List → port 8000 already open hai"
Write-Host "   [2] VM par password badlein:"
Write-Host "       ssh -i $KeyPath ${target}"
Write-Host "       sudo nano /opt/gilclinic/.env   (SUPER_ADMIN_PASSWORD / CEO_PASSWORD)"
Write-Host "       sudo systemctl restart gilclinic"
Write-Host "   [3] Backup laptop par kheenchne ke liye (hafte mein ek baar):"
Write-Host "       .\deploy_remote.ps1 -VmIp $VmIp -KeyPath $KeyPath -Mode PullBackup"
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
