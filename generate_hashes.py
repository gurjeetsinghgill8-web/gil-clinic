import os
import hashlib
import zipfile
import datetime

WORKSPACE = r"c:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
VAULT_DIR = os.path.join(WORKSPACE, "LEGAL_IP_PROTECTION_VAULT_2026-09-24")
os.makedirs(VAULT_DIR, exist_ok=True)

# List of critical files to hash for the IP Manifest
CORE_FILES = [
    "FIR_PRODUCT_DEVELOPMENT.md",
    "GIL_CLINIC_PRODUCT_DEVELOPMENT.md",
    "SMART_OPD_MASTER_REFERENCE.md",
    "PRODUCT_UPGRADATION_PLAN.md",
    "V2_ARCHITECTURE.md",
    "MEMORY.md",
    "main_v2.py",
    "llm_harness.py",
    "pa_deploy.py",
    "start_tunnel.py",
    os.path.join("src", "ai_engine", "provider_router.py"),
    os.path.join("src", "presentation", "opd", "routes", "opd_routes.py"),
    os.path.join("src", "infrastructure", "opd", "models", "opd_models.py"),
    os.path.join("templates", "opd", "dashboard.html"),
    os.path.join("static", "js", "ai_gateway.js"),
    os.path.join("patient-pwa", "app.js"),
    os.path.join("patient-pwa", "index.html"),
]

def get_file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

# Collect file hashes
hash_manifest = []
for rel_path in CORE_FILES:
    full_path = os.path.join(WORKSPACE, rel_path)
    if os.path.exists(full_path):
        sha = get_file_hash(full_path)
        size = os.path.getsize(full_path)
        hash_manifest.append((rel_path.replace("\\", "/"), sha, size))
    else:
        print(f"Warning: File not found: {rel_path}")

print(f"Hashed {len(hash_manifest)} core files successfully.")

# Save manifest to text
manifest_path = os.path.join(VAULT_DIR, "SHA256_MANIFEST.txt")
with open(manifest_path, "w", encoding="utf-8") as f:
    f.write(f"GHOS / GIL CLINIC CRYPTOGRAPHIC SHA-256 MANIFEST\n")
    f.write(f"Timestamp: 2026-09-24T17:35:00+05:30\n")
    f.write(f"Owner: Dr. Gurjeet Singh Gill (Gurjas Singh Gill)\n")
    f.write(f"="*80 + "\n\n")
    for path, sha, size in hash_manifest:
        f.write(f"{sha}  [{size:>10} bytes]  {path}\n")

print(f"Manifest written to {manifest_path}")
