import os
import zipfile

WORKSPACE = r"c:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
DESKTOP = r"C:\Users\pc\Desktop"

ZIP_STANDARD = os.path.join(DESKTOP, "GHOS_INSPECTION_PACKAGE_FOR_ANUJ_JI.zip")
ZIP_GMAIL_SAFE = os.path.join(DESKTOP, "GHOS_INSPECTION_PACKAGE_GMAIL_SAFE.zip")

EXCLUDE_DIRS = {
    ".git", ".railway", ".railway-config-pull-12800", ".pytest_cache", 
    "node_modules", "__pycache__", "LEGAL_IP_PROTECTION_VAULT_2026-09-24", 
    ".agents", ".zcode"
}
EXCLUDE_EXTS = {".exe", ".db", ".zip", ".pyc"}
GMAIL_BLOCKED_EXTS = {".js", ".bat", ".ps1", ".sh", ".cmd", ".vbs"}

restore_script_content = '''"""
Run this script to restore file extensions if downloaded via Gmail:
Usage: python RESTORE_FILES.py
"""
import os

BLOCKED_CONVERSIONS = [".js.txt", ".bat.txt", ".ps1.txt", ".sh.txt", ".cmd.txt"]

for root, dirs, files in os.walk("."):
    for file in files:
        for ext in BLOCKED_CONVERSIONS:
            if file.endswith(ext):
                original_name = file[:-4]
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, original_name)
                os.rename(old_path, new_path)
                print(f"Restored: {file} -> {original_name}")

print("All original file extensions restored successfully!")
'''

print("1. Creating Standard Zip for WhatsApp / Drive / Direct Sharing...")
count_std = 0
with zipfile.ZipFile(ZIP_STANDARD, "w", zipfile.ZIP_DEFLATED) as z:
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
                z.write(full_path, arcname=rel_path)
                count_std += 1
            except Exception as e:
                pass

print(f"Standard ZIP ready: {count_std} files. Size: {os.path.getsize(ZIP_STANDARD)/(1024*1024):.2f} MB")

print("\n2. Creating Gmail-Safe Zip (Masked extensions for Gmail)...")
count_safe = 0
with zipfile.ZipFile(ZIP_GMAIL_SAFE, "w", zipfile.ZIP_DEFLATED) as z:
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
                if ext in GMAIL_BLOCKED_EXTS:
                    arc_path = rel_path + ".txt"
                else:
                    arc_path = rel_path
                z.write(full_path, arcname=arc_path)
                count_safe += 1
            except Exception as e:
                pass

print(f"Gmail-Safe ZIP ready: {count_safe} files. Size: {os.path.getsize(ZIP_GMAIL_SAFE)/(1024*1024):.2f} MB")
print("\nBoth inspection packages are now on Desktop!")
