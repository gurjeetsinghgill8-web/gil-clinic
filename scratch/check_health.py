import requests, time

for i in range(1, 20):
    try:
        r = requests.get('https://cardioqueue-production.up.railway.app/health')
        print(f"Check #{i}: Status Code = {r.status_code} | Body = {r.text[:100]}")
        if r.status_code == 200 and "2026.08.02" in r.text:
            print("🎉 SUCCESS: Live Railway container HAS SWAPPED to the new build!")
            break
    except Exception as e:
        print(f"Check #{i} error: {e}")
    time.sleep(10)
