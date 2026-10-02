import requests

pins = ["5554", "1234", "1010"]

for pin in pins:
    s = requests.Session()
    r1 = s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': pin}, allow_redirects=True)
    r2 = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
    html = r2.text
    size = len(html.encode('utf-8'))
    has_cam = "camera-file-input" in html or "Camera Snap" in html
    print(f"PIN {pin}: Redirect URL = {r1.url} | Dashboard Status = {r2.status_code} | Size = {size} | Has Camera? = {has_cam}")
