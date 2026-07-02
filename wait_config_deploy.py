import time
import requests

url = "https://gurjeetsinghgill8-web.github.io/gil-clinic/pwa/index.html"

print("Polling live page to verify config deploy...")
for i in range(12):
    time.sleep(10)
    try:
        r = requests.get(url + "?v=" + str(time.time()))
        is_live = "cardioqueue_version" in r.text
        print(f"Poll {i+1}: is_live={is_live}")
        if is_live:
            print("VERIFICATION SUCCESSFUL! Jekyll Deploy finished and cache buster is live.")
            break
    except Exception as e:
        print("Error:", e)
