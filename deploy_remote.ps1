# deploy_remote.ps1 - GIL CLINIC one-command deploy (Windows laptop -> Oracle/Google VM)
#
# After the Oracle VM is created, on this laptop just run:
#   .\deploy_remote.ps1 -VmIp 123.45.67.89 -KeyPath .\gil-clinic-key.key
#
# The script:
#   1. Tests the SSH connection
#   2. Uploads deploy_oracle.sh to the VM and runs it with sudo
#   3. Polls the public health URL for up to 2 minutes
#   4. Pulls the VM admin credentials back to the laptop
#
# Modes:
#   -Mode Deploy      (default) - full setup as above
#   -Mode PushData    - migrate the local patient DB into the VM's permanent data folder
#                       (VM's existing DB is backed up first as pre-migrate-<timestamp>.db)
#   -Mode PullBackup  - copy the VM's latest backup to .\vm_backups\
#   -Mode Status      - one-shot report: service, data, backups, disk
#
# Requirements: VM running (Ubuntu 22.04), ports 22 + 8000 open,
# SSH private key saved on this laptop.
#
# NOTE: This file is deliberately ASCII-only so it parses correctly in both
# Windows PowerShell 5.1 and PowerShell 7.
param(
    [Parameter(Mandatory = $true)]
    [string]$VmIp,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [ValidateSet("Deploy", "PullBackup", "PushData", "Status")]
    [string]$Mode = "Deploy",

    [string]$User = "ubuntu",

    [string]$LocalDb = ".\ghos_dev.db"
)

$ErrorActionPreference = "Stop"
$sshBase = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes")
$target = "${User}@${VmIp}"

function Run-Ssh([string]$command) {
    & ssh @sshBase $target $command
    if ($LASTEXITCODE -ne 0) { throw "SSH command failed: $command" }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GIL CLINIC - VM Deploy Helper" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VM:   ${VmIp}"
Write-Host "  User: ${User}"
Write-Host "  Key:  ${KeyPath}"
Write-Host ""

if (-not (Test-Path $KeyPath)) { throw "SSH key not found: $KeyPath" }

if ($Mode -eq "PullBackup") {
    Write-Host "==> [Backup pull] Fetching latest backup from VM..."
    New-Item -ItemType Directory -Force -Path ".\vm_backups" | Out-Null
    $latest = & ssh @sshBase $target "ls -t /opt/gilclinic/data/backups/*.db 2>/dev/null | head -1"
    if (-not $latest) { throw "No backup found on VM (or /opt/gilclinic/data/backups is empty)" }
    $latest = $latest.Trim()
    Write-Host "   Latest backup: $latest"
    & scp @sshBase "${target}:${latest}" ".\vm_backups\"
    if ($LASTEXITCODE -ne 0) { throw "scp failed" }
    Write-Host "   [OK] Backup saved to .\vm_backups\" -ForegroundColor Green
    exit 0
}

if ($Mode -eq "PushData") {
    Write-Host "==> [PushData] Migrating local DB to the VM's permanent data folder..."
    if (-not (Test-Path $LocalDb)) { throw "Local DB not found: $LocalDb" }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Write-Host "   [1/4] Stopping VM service + backing up existing VM data..."
    Run-Ssh "sudo systemctl stop gilclinic 2>/dev/null; sudo cp /opt/gilclinic/data/ghos_prod.db /opt/gilclinic/data/backups/pre-migrate-${stamp}.db 2>/dev/null; echo VM_READY"
    Write-Host "   [2/4] Uploading local DB ($LocalDb)..."
    & scp @sshBase $LocalDb "${target}:/tmp/ghos_upload.db"
    if ($LASTEXITCODE -ne 0) { throw "scp failed" }
    Write-Host "   [3/4] Placing into VM data folder + permissions + starting service..."
    Run-Ssh "sudo mv /tmp/ghos_upload.db /opt/gilclinic/data/ghos_prod.db; sudo chown root:root /opt/gilclinic/data/ghos_prod.db; sudo chmod 644 /opt/gilclinic/data/ghos_prod.db; sudo systemctl start gilclinic; echo DATA_PLACED"
    Write-Host "   [4/4] Health check..."
    $ok = $false
    for ($i = 0; $i -lt 24; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://${VmIp}:8000/health" -UseBasicParsing -TimeoutSec 10
            if ($r.StatusCode -eq 200 -and $r.Content -match '"ok"') { $ok = $true; break }
        } catch { }
        Start-Sleep -Seconds 5
    }
    if (-not $ok) { throw "Health check FAILED after migrate - check VM logs: journalctl -u gilclinic -n 50" }
    Write-Host "   [OK] Data migrated + app LIVE: http://${VmIp}:8000" -ForegroundColor Green
    Write-Host "   Note: admin password is now the VM .env one (SUPER_ADMIN_PASSWORD / CEO_PASSWORD)." -ForegroundColor Yellow
    exit 0
}

if ($Mode -eq "Status") {
    Write-Host "==> [Status] Full VM report..."
    Run-Ssh "echo '--- service ---'; systemctl is-active gilclinic; systemctl status gilclinic --no-pager -n 8 | tail -n 12; echo '--- data ---'; ls -lh /opt/gilclinic/data/ 2>/dev/null; echo '--- backups ---'; ls -lt /opt/gilclinic/data/backups/ 2>/dev/null | head -n 8; echo '--- disk ---'; df -h /opt/gilclinic | tail -n 2"
    exit 0
}

# --- Step 1: SSH test -------------------------------------------------
Write-Host "==> [1/5] SSH test..."
Run-Ssh "echo VM_OK; uname -a"

# --- Step 2: Upload + run deploy script ------------------------------
Write-Host "==> [2/5] Uploading deploy_oracle.sh to VM..."
& scp @sshBase ".\deploy_oracle.sh" "${target}:~/"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }
Write-Host "   [OK] Uploaded"

Write-Host "==> [3/5] Running deploy on VM (5-10 min, first run)..."
Run-Ssh "sudo bash ~/deploy_oracle.sh"

# --- Step 4: Health check on public IP --------------------------------
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
if (-not $ok) { throw "Health check FAILED - open port 8000 in Oracle Security List, then retry" }
Write-Host "   [OK] App LIVE: http://${VmIp}:8000" -ForegroundColor Green

# --- Step 5: Pull admin credentials -----------------------------------
Write-Host "==> [5/5] Pulling admin credentials from VM..."
New-Item -ItemType Directory -Force -Path ".\vm_credentials" | Out-Null
& scp @sshBase "${target}:/opt/gilclinic/admin_credentials.txt" ".\vm_credentials\"
if ($LASTEXITCODE -ne 0) {
    Write-Host "   [WARN] credentials file not found (check VM console)"
} else {
    Write-Host "   [OK] Saved: .\vm_credentials\admin_credentials.txt" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DEPLOY COMPLETE!"
Write-Host "  Website: http://${VmIp}:8000"
Write-Host ""
Write-Host "  One-time follow-ups:"
Write-Host "   [1] Oracle console - Security List - port 8000 open"
Write-Host "   [2] Change VM passwords:"
Write-Host "       ssh -i $KeyPath ${target}"
Write-Host "       sudo nano /opt/gilclinic/.env   (SUPER_ADMIN_PASSWORD / CEO_PASSWORD)"
Write-Host "       sudo systemctl restart gilclinic"
Write-Host "   [3] Weekly laptop backup pull:"
Write-Host "       .\deploy_remote.ps1 -VmIp $VmIp -KeyPath $KeyPath -Mode PullBackup"
Write-Host "   [4] Migrate local patient data:"
Write-Host "       .\deploy_remote.ps1 -VmIp $VmIp -KeyPath $KeyPath -Mode PushData"
Write-Host "============================================================" -ForegroundColor Cyan
