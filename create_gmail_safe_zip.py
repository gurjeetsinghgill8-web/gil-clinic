import os
import zipfile

WORKSPACE = r"c:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
VAULT_DIR = os.path.join(WORKSPACE, "LEGAL_IP_PROTECTION_VAULT_2026-09-24")

GMAIL_SAFE_ZIP = os.path.join(VAULT_DIR, "GHOS_FULL_CODEBASE_GMAIL_READY_2026-09-24.zip")

EXCLUDE_DIRS = {
    ".git", ".railway", ".railway-config-pull-12800", ".pytest_cache", 
    "node_modules", "__pycache__", "LEGAL_IP_PROTECTION_VAULT_2026-09-24", 
    ".agents", ".zcode"
}
EXCLUDE_EXTS = {".exe", ".db", ".zip", ".pyc"}
GMAIL_BLOCKED_EXTS = {".js", ".bat", ".ps1", ".sh", ".cmd", ".vbs"}

restore_script_content = '''"""
Run this script to restore all sanitized file extensions (.js.txt -> .js, .bat.txt -> .bat, etc.)
Usage: python RESTORE_FILES.py
"""
import os

BLOCKED_CONVERSIONS = [".js.txt", ".bat.txt", ".ps1.txt", ".sh.txt", ".cmd.txt"]

for root, dirs, files in os.walk("."):
    for file in files:
        for ext in BLOCKED_CONVERSIONS:
            if file.endswith(ext):
                original_name = file[:-4]  # Remove .txt
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, original_name)
                os.rename(old_path, new_path)
                print(f"Restored: {file} -> {original_name}")

print("All files restored successfully!")
'''

print(f"Creating GMAIL-READY ZIP: {GMAIL_SAFE_ZIP} ...")

total_added = 0
converted_count = 0

with zipfile.ZipFile(GMAIL_SAFE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    # Add restore script
    z.writestr("RESTORE_FILES.py", restore_script_content)
    
    for root, dirs, files in os.walk(WORKSPACE):
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
                
                # If Gmail blocks this extension, append .txt so Gmail allows it
                if ext in GMAIL_BLOCKED_EXTS:
                    arc_path = rel_path + ".txt"
                    converted_count += 1
                else:
                    arc_path = rel_path
                    
                z.write(full_path, arcname=arc_path)
                total_added += 1
            except Exception as e:
                print(f"Skipping {file}: {e}")

size_mb = os.path.getsize(GMAIL_SAFE_ZIP) / (1024 * 1024)
print(f"GMAIL-READY ZIP created successfully!")
print(f"Total files: {total_added} ({converted_count} script files safely masked with .txt)")
print(f"Zip Size: {size_mb:.2f} MB")
