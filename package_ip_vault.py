import os
import zipfile
import shutil

WORKSPACE = r"c:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
VAULT_DIR = os.path.join(WORKSPACE, "LEGAL_IP_PROTECTION_VAULT_2026-09-24")

# 1. Package Legal Docs ZIP
LEGAL_ZIP = os.path.join(VAULT_DIR, "GHOS_LEGAL_IP_VAULT_2026-09-24.zip")
print(f"Creating Legal ZIP: {LEGAL_ZIP} ...")

with zipfile.ZipFile(LEGAL_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for filename in os.listdir(VAULT_DIR):
        if filename.endswith(".zip") or filename.startswith("."):
            continue
        file_path = os.path.join(VAULT_DIR, filename)
        if os.path.isfile(file_path):
            z.write(file_path, arcname=filename)
            print(f"  + Added: {filename}")

print(f"Legal ZIP created. Size: {os.path.getsize(LEGAL_ZIP):,} bytes.")

# 2. Package Full Codebase Snapshot ZIP
CODEBASE_ZIP = os.path.join(VAULT_DIR, "GHOS_FULL_CODEBASE_SNAPSHOT_2026-09-24.zip")
print(f"\nCreating Full Codebase Snapshot ZIP: {CODEBASE_ZIP} ...")

# Exclude patterns
EXCLUDE_DIRS = {
    ".git", ".railway", ".railway-config-pull-12800", ".pytest_cache", 
    "node_modules", "__pycache__", "LEGAL_IP_PROTECTION_VAULT_2026-09-24", 
    ".agents", ".zcode"
}
EXCLUDE_EXTS = {".exe", ".db", ".zip", ".pyc"}

total_files_added = 0
with zipfile.ZipFile(CODEBASE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(WORKSPACE):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if file.lower() in ("nul", "con", "prn", "aux", "com1", "lpt1"):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue
            if file == "cloudflared.exe" or file.endswith(".db"):
                continue
                
            full_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(full_path, WORKSPACE)
                z.write(full_path, arcname=rel_path)
                total_files_added += 1
            except Exception as e:
                print(f"Skipping {file}: {e}")

codebase_size_mb = os.path.getsize(CODEBASE_ZIP) / (1024 * 1024)
print(f"Full Codebase ZIP created: {total_files_added} files added.")
print(f"Codebase ZIP Size: {codebase_size_mb:.2f} MB (Well within Gmail 25 MB limit!)")
