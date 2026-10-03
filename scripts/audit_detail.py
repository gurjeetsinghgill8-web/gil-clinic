import json
import requests

d = json.load(open('scripts/.audit_probe.json', encoding='utf-8'))
print("=== non-200 / non-redirect (the interesting ones) ===")
for r in d:
    if r['status'] in (400, 401, 404, 410, 422, 500) or r['status'] == 0:
        print(f"  {r['status']:>4}  {r['path']:<55} -> {r.get('redirect_to') or r.get('error') or ''}")

print("\n=== queue notes 500 body ===")
r = requests.get('https://gillhopitalsoftware1.pythonanywhere.com/api/v1/queue/notes/0', timeout=45, allow_redirects=False)
print('status', r.status_code)
print(r.text[:600])
