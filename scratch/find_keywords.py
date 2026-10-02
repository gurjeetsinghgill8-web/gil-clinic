import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

s = requests.Session()
login_resp = s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '1234'}, allow_redirects=True)
dash_resp = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
html = dash_resp.text

lines = html.split('\n')
print("Total lines:", len(lines))
for idx, line in enumerate(lines):
    if "Camera Snap" in line or "Gallery Upload" in line or "Take Live Camera" in line or "Upload from Gallery" in line:
        print(f"Line {idx}: {line.strip()}")
