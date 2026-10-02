import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

s = requests.Session()
s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '5554'}, allow_redirects=True)
r = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
live_html = r.text

with open('templates/opd/dashboard.html', 'r', encoding='utf-8') as f:
    local_html = f.read()

print("Local HTML byte size:", len(local_html.encode('utf-8')))
print("Live HTML byte size:", len(live_html.encode('utf-8')))

# Find differences
local_lines = local_html.splitlines()
live_lines = live_html.splitlines()

print(f"Local line count: {len(local_lines)} | Live line count: {len(live_lines)}")

print("\n--- First 10 lines of Local HTML ---")
for l in local_lines[:10]:
    print(l)

print("\n--- First 10 lines of Live HTML ---")
for l in live_lines[:10]:
    print(l)
