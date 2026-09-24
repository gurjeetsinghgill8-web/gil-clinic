"""
Automated Email Backup Script for Dr. Gurjeet Singh Gill
Sends the IP Vault and Codebase Snapshots to your two emails:
- gurjeetsinghgill8@gmail.com
- mcgillpharma@gmail.com

Instructions:
1. Generate a 16-character Google App Password from: https://myaccount.google.com/apppasswords
2. Run this script: python send_gmail_backup.py
3. It will prompt for your App Password (or pass it via environment variable GMAIL_APP_PASS)
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

SENDER_EMAIL = "gurjeetsinghgill8@gmail.com"
RECIPIENTS = ["gurjeetsinghgill8@gmail.com", "mcgillpharma@gmail.com"]

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
TXT_PATH = os.path.join(VAULT_DIR, "04_EMAIL_TO_SELF_PRIOR_ART_PROOF.txt")
ZIP_LEGAL = os.path.join(VAULT_DIR, "GHOS_LEGAL_IP_VAULT_2026-09-24.zip")
ZIP_CODE = os.path.join(VAULT_DIR, "GHOS_FULL_CODEBASE_SNAPSHOT_2026-09-24.zip")

def main():
    print("=" * 70)
    print("GHOS / GIL CLINIC — AUTOMATED SECURE IP BACKUP SENDER")
    print("=" * 70)
    
    app_password = os.environ.get("GMAIL_APP_PASS")
    if not app_password:
        import getpass
        print("\nNote: Use a Google App Password (not your normal Gmail login password).")
        print("Create one in 30 seconds at: https://myaccount.google.com/apppasswords")
        app_password = getpass.getpass("Enter 16-character Google App Password: ").strip()

    if not app_password:
        print("Error: No password provided. Exiting.")
        return

    # Read the text body
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        body_text = f.read()

    msg = EmailMessage()
    msg["Subject"] = "[OFFICIAL IP RECORD & PRIOR ART] GHOS / GIL CLINIC - Dr. Gurjeet Singh Gill - 24-Sep-2026 17:35 IST"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS)
    msg.set_content(body_text)

    # Attach legal zip
    if os.path.exists(ZIP_LEGAL):
        with open(ZIP_LEGAL, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="zip", filename="GHOS_LEGAL_IP_VAULT_2026-09-24.zip")
            print("Attached: GHOS_LEGAL_IP_VAULT_2026-09-24.zip")

    # Attach code zip
    if os.path.exists(ZIP_CODE):
        with open(ZIP_CODE, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="zip", filename="GHOS_FULL_CODEBASE_SNAPSHOT_2026-09-24.zip")
            print("Attached: GHOS_FULL_CODEBASE_SNAPSHOT_2026-09-24.zip")

    print("\nConnecting to Gmail SMTP server (smtp.gmail.com:465)...")
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, app_password)
            server.send_message(msg)
            print("\n SUCCESS! Email sent successfully to:")
            for r in RECIPIENTS:
                print(f"   -> {r}")
            print("\nCheck your inbox & sent folder. Your cryptographic proof of prior art is now locked on Google servers.")
    except Exception as e:
        print(f"\n❌ Error sending email: {e}")
        print("You can also simply open Gmail in your browser, copy the text from 04_EMAIL_TO_SELF_PRIOR_ART_PROOF.txt, attach the two zip files, and click send!")

if __name__ == "__main__":
    main()
