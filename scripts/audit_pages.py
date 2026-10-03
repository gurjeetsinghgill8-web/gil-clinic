import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
routes = json.loads((ROOT / "scripts" / ".audit_routes.json").read_text(encoding="utf-8"))

# HTML page routes = GET, not /api, not /static, not docs, not json
pages = [r for r in routes if "GET" in r["methods"] and "/api" not in r["path"]
         and not r["path"].startswith("/static")
         and r["path"] not in ("/openapi.json", "/docs", "/redoc")
         and not r["path"].endswith((".json", ".js", ".png", ".svg", ".ico"))]

print(f"TOTAL routes: {len(routes)}")
print(f"HTML/UI page routes: {len(pages)}")
print()
print("== PAGE ROUTES (what a user can actually open) ==")
for p in sorted(pages, key=lambda r: r["path"]):
    print(f"  {p['path']:<40} {p['owner'].split('.')[-1] if p['owner'] else ''}")

# staff vs opd counts
staff = [p for p in pages if p["path"].startswith("/staff")]
opd = [p for p in pages if p["path"].startswith("/opd")]
print(f"\n/staff/* pages: {len(staff)}")
print(f"/opd/* pages:  {len(opd)}")

# static files that templates reference but that don't exist
print("\n== static JS/CSS referenced by dashboard/base.html ==")
for js in ("static/dashboard/app.js", "static/dashboard/style.css",
           "static/js/whatsapp_helper.js", "static/js/ai_gateway.js"):
    exists = (ROOT / js).exists()
    print(f"  {'OK ' if exists else 'MISSING'}  {js}")
