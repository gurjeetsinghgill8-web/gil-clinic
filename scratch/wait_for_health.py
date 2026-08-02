import requests, time, sys

print("Waiting for Railway container build to swap...")
for i in range(1, 25):
    try:
        r = requests.get('https://cardioqueue-production.up.railway.app/health', timeout=5)
        print(f"Check #{i}: Status = {r.status_code} | Text = {r.text}")
        if r.status_code == 200 and "2026.08.02" in r.text:
            print("🎉 SUCCESS! Railway container HAS SWAPPED to latest build!")
            sys.exit(0)
    except Exception as e:
        print(f"Check #{i} error: {e}")
    time.sleep(10)

print("Still waiting for Railway to deploy...")
