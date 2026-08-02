import requests

s = requests.Session()
login_resp = s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '1234'}, allow_redirects=True)
dash_resp = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
html = dash_resp.text

print("HTML byte length:", len(html))
print("'Camera Snap' in HTML?:", "Camera Snap" in html)
print("'Gallery Upload' in HTML?:", "Gallery Upload" in html)
print("'camera-file-input' in HTML?:", "camera-file-input" in html)

if "camera-file-input" in html:
    print("SUCCESS: Camera and Gallery buttons are LIVE on Railway production!")
else:
    print("NOT YET LIVE: Searching for matching text...")
    idx = html.find("New Prescription")
    print("Snippet around New Prescription:\n", html[idx:idx+1000] if idx != -1 else "Not found")
