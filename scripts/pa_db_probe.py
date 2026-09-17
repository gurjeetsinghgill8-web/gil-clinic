import os, sqlite3, requests, tempfile
tok = open("pa_token.txt").read().strip()
H = {"Authorization": "Token " + tok}
U = "https://www.pythonanywhere.com/api/v0/user/gillhopitalsoftware1/files/path/home/gillhopitalsoftware1/gil-clinic/ghos_prod.db"
r = requests.get(U, headers=H, timeout=120)
print("db download:", r.status_code, len(r.content), "bytes")
if r.ok and len(r.content) > 2000:
    tmp = os.path.join(tempfile.gettempdir(), "gil_pa_probe.db")
    open(tmp, "wb").write(r.content)
    con = sqlite3.connect(tmp)
    cur = con.cursor()
    tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("tables:", ", ".join(tables))
    for t in ["patients", "opd_prescriptions", "queue_entries", "patient_readings", "patient_portal_links", "patient_shares", "opd_settings", "opd_lab_reports"]:
        if t in tables:
            print(f"  {t}: {cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rows")
    con.close()
    os.remove(tmp)
