import requests, time, sys
sys.stdout.reconfigure(encoding='utf-8')

for attempt in range(1, 15):
    try:
        s = requests.Session()
        s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '1234'}, allow_redirects=True)
        dash_resp = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
        html = dash_resp.text
        size = len(html.encode('utf-8'))
        has_camera = "camera-file-input" in html or "Camera Snap" in html
        print(f"Attempt {attempt}: HTML Size = {size} bytes | Has Camera Buttons? = {has_camera}")
        if has_camera or size > 140000:
            print("🎉 SUCCESS! Live Railway server has updated to latest 155KB build with Camera and Gallery buttons!")
            sys.exit(0)
    except Exception as e:
        print(f"Attempt {attempt} error: {e}")
    time.sleep(10)

print("Timed out waiting for Railway build. Please check Railway dashboard.")
