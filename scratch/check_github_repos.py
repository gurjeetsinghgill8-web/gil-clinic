import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

repos = [
    "gurjeetsinghgill8-web/gil-clinic",
    "gurjeetsinghgill8-web/cardioqueue",
    "gurjeetsinghgill8-web/smart-opd2",
    "gurjeetsinghgill8-web/new-opd-EXTENDED-B"
]

for repo in repos:
    url = f"https://api.github.com/repos/{repo}/commits/main"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        sha = data.get("sha", "")[:7]
        msg = data.get("commit", {}).get("message", "").split("\n")[0]
        date = data.get("commit", {}).get("author", {}).get("date", "")
        print(f"Repo: {repo} | Branch: main | SHA: {sha} | Date: {date} | Message: {msg}")
    else:
        url_m = f"https://api.github.com/repos/{repo}/commits/master"
        rm = requests.get(url_m)
        if rm.status_code == 200:
            data = rm.json()
            sha = data.get("sha", "")[:7]
            msg = data.get("commit", {}).get("message", "").split("\n")[0]
            date = data.get("commit", {}).get("author", {}).get("date", "")
            print(f"Repo: {repo} | Branch: master | SHA: {sha} | Date: {date} | Message: {msg}")
        else:
            print(f"Repo: {repo} | Status: {r.status_code}")
