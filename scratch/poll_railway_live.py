import requests, time, datetime

print("Polling Railway live server for template update...")
start_time = datetime.datetime.now()

for i in range(1, 20):
    try:
        s = requests.Session()
        s.post('https://cardioqueue-production.up.railway.app/opd/login', data={'pin': '1234'}, allow_redirects=True)
        r = s.get('https://cardioqueue-production.up.railway.app/opd/dashboard')
        text = r.text
        size = len(text)
        has_camera = "camera-file-input" in text or "Camera Snap" in text
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now_str}] Check #{i}: Size={size} | Camera Buttons Live? = {has_camera}")
        if has_camera or size > 140000:
            print(f"🎉 DEPLOYMENT LIVE AT {now_str}! Railway successfully deployed commit c238624!")
            break
    except Exception as e:
        print(f"Check #{i} error: {e}")
    time.sleep(15)
