import time
import requests

url = "https://gurjeetsinghgill8-web.github.io/gil-clinic/pwa/index.html"

print("Polling live URL for branch deploy verification...")
for i in range(15):
    time.sleep(10)
    try:
        r = requests.get(url + "?v=" + str(time.time()))
        is_live = "cardioqueue_version" in r.text
        print(f"Poll {i+1}: is_live={is_live}")
        if is_live:
            print("VERIFICATION SUCCESSFUL! Deploy completed and cache buster is active.")
            break
    except Exception as e:
        print("Error:", e)
