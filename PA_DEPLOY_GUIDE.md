# GIL CLINIC — PythonAnywhere Free Deploy Guide (BINA CARD, 24/7)
## 29-Aug-2026 · Verified against PA official ASGI beta docs · Cost ₹0/माह

> ⚠️ PythonAnywhere ki ASGI (FastAPI) hosting **beta** hai aur normal "Web" tab se nahi,
> **`pa` command-line tool** se hoti hai. Neeche steps PA ki official help page
> (help.pythonanywhere.com/pages/ASGICommandLine) se verify kiye hue hain.

---

## Kya milega / kya nahi (seedha sach)

| Cheez | PythonAnywhere FREE |
|---|---|
| Card | ❌ **Nahi chahiye** — sirf email + password |
| 24/7 | ✅ Hamesha chalta hai (sota nahi) |
| URL | `https://gillhopitalsoftware1.pythonanywhere.com` |
| Storage | 512MB total (hamari DB ~0.5MB — bahut hai) |
| CPU | ~100 sec/day free limit — heavy clinic day ke END mein kabhi-kabhi limit lag sakti hai (agle din reset). Tab $5/mo Hacker plan ya Oracle (jab card aaye) |
| AI APIs | Free account par outbound sirf **whitelist** sites — Groq/WhatsApp/Gemini ke liye ek request bhejni hogi (Step 9) |
| Backup | Free = **1 scheduled task per day** — backup_now.py daily chalega |
| Static files | ASGI beta mein static mapping **nahi** — hamara app khud static serve karta hai, koi dikkat nahi |

---

## Step 1: Account (ho gaya ✅)
Username: `gillhopitalsoftware1`

## Step 2: API token banao (1 min — `pa` CLI ke liye zaroori)
1. `pythonanywhere.com` → **Account** tab → **API token** tab → **Create API token**
2. Token dikhega — copy karne ki zaroorat nahi, Bash console ke andar khud available ho jata hai

## Step 3: Code + venv + dependencies (Bash console, 10 min)
```
git clone https://github.com/gurjeetsinghgill8-web/gil-clinic.git
cd ~/gil-clinic
mkvirtualenv gilclinic --python=python3.10
pip install -r requirements.txt
pip install --upgrade pythonanywhere
```
- `python3.10` nahi hai to `python3.11` ya `python3.12` try karo (jo list dikhe)
- `pythonanywhere` install karte waqt `typing-extensions` ka error aaye to **ignore** kar do (PA ki docs khud bolti hain)
- Ab ek naya command mil gaya hai: **`pa`**

## Step 4: Website create karo (1 min — YAHI ASLI STEP HAI)
Bash mein (poori line ek saath, quotes ke saath):
```
pa website create --domain gillhopitalsoftware1.pythonanywhere.com --command '/home/gillhopitalsoftware1/.virtualenvs/gilclinic/bin/uvicorn --app-dir /home/gillhopitalsoftware1/gil-clinic --uds ${DOMAIN_SOCKET} main_v2:app'
```
- `${DOMAIN_SOCKET}` ko **aisa hi rehne do** — PA khud replace karta hai
- Success par: `All done! Your site is now live at gillhopitalsoftware1.pythonanywhere.com`
- **Note:** pehle kuch seconds 404 dikh sakta hai (PA ka known bug) — browser refresh karo

## Step 5: `.env` banao (2 min)
Bash mein:
```
cd ~/gil-clinic
nano .env
```
Ye content paste karo (GROQ key apne laptop ke `.env` se copy karo):
```
GROQ_API_KEY=<laptop ke .env wali key>
APP_BASE_URL=https://gillhopitalsoftware1.pythonanywhere.com
GHOS_DB_URL=sqlite:////home/gillhopitalsoftware1/gil-clinic/ghos_prod.db
GHOS_DB_URL_ASYNC=sqlite+aiosqlite:////home/gillhopitalsoftware1/gil-clinic/ghos_prod.db
SUPER_ADMIN_PASSWORD=ApnaStrongPass123
CEO_PASSWORD=ApnaStrongPass456
SECRET_KEY=gilclinic2026secretkeychange897123
GHOS_AI_KEYS_SECRET=gilclinicAikeysSecretChange4567123
SYSTEM_AI_FALLBACK_ENABLED=false
```
Save: `Ctrl+O` → Enter → `Ctrl+X`
(DB ka absolute path isliye — PA par uvicorn ka CWD home dir hota hai, project dir nahi)

## Step 6: Reload + health check
```
pa website reload --domain gillhopitalsoftware1.pythonanywhere.com
```
Browser: **`https://gillhopitalsoftware1.pythonanywhere.com/health`** → `{"status":"ok"...}` = LIVE 🎉

**Error aaye to ye dekho:**
```
tail -n 30 /var/log/gillhopitalsoftware1.pythonanywhere.com.error.log
```
Poora output paste kar dena — main debug kar dunga.

## Step 7: Purana data migrate (optional)
- Laptop se `pa_data_upload.zip` bhejo (koi bhi tarah — PA **Files** tab → Upload)
- Bash mein unzip:
  ```
  cd ~/gil-clinic
  unzip ~/pa_data_upload.zip -d /tmp/pa_upload
  cp /tmp/pa_upload/ghos_prod.db ~/gil-clinic/ghos_prod.db
  pa website reload --domain gillhopitalsoftware1.pythonanywhere.com
  ```

## Step 8: Daily backup task (2 min)
- **Tasks** tab → scheduled task (daily, time 23:30 UTC):
  ```
  python /home/gillhopitalsoftware1/gil-clinic/backup_now.py
  ```
- Free = 1 task/day — kaafi hai. Backups `backups/` mein 30 din tak rahenge

## Step 9: API whitelist request (AI + WhatsApp ke liye)
- `pa_whitelist_request.txt` (project mein ready hai) ka text copy karke
  pythonanywhere.com → **Help** → **Send feedback** mein paste kar ke bhejo
- Approved hone tak AI features limited; baaki sab (queue/tokens/reports) normal

## WhatsApp Cloud API (optional — Meta free)
`CLOUD_DEPLOY_GUIDE.md` Part 4 se Phone number ID + token le kar `.env` mein daalo:
```
WHATSAPP_PHONE_NUMBER_ID=<id>
WHATSAPP_ACCESS_TOKEN=<token>
```
→ `pa website reload --domain gillhopitalsoftware1.pythonanywhere.com`

---

## Go-Live Checklist (PythonAnywhere)
- [ ] `/health` 200 OK
- [ ] Admin login (SUPER_ADMIN_PASSWORD se)
- [ ] Patient register → tracking link `https://gillhopitalsoftware1.pythonanywhere.com/track/...` phone par ghar se khulta hai
- [ ] Backup task ka pehla run ho gaya (backups/ folder check)
- [ ] Whitelist request bhej di

**Laptop + Cloudflare Tunnel** abhi bhi chal raha hai — PA live hone tak dono saath chal sakte hain.
