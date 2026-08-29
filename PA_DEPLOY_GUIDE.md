# GIL CLINIC — PythonAnywhere Free Deploy Guide (BINA CARD, 24/7)
## 29-Aug-2026 · Step-by-step · Cost ₹0/माह · Kabhi nahi sota

---

## Kya milega / kya nahi (seedha sach)

| Cheez | PythonAnywhere FREE |
|---|---|
| Card | ❌ **Nahi chahiye** — sirf email + password |
| 24/7 | ✅ Hamesha chalta hai (sota nahi) |
| URL | `https://<aapka-username>.pythonanywhere.com` |
| Storage | 512MB total (hamari DB ~0.5MB — bahut hai) |
| CPU | ~100 sec/day free limit — heavy clinic day ke END mein kabhi-kabhi limit lag sakti hai (agle din reset). Tab $5/mo Hacker plan ya Oracle (jab card aaye) |
| AI APIs | Free account par outbound sirf **whitelist** sites — Groq/WhatsApp/Gemini ke liye ek request bhejni hogi (Step 8) |
| Backup | Free = **1 scheduled task per day** — backup_now.py daily chalega |

---

## Step 1: Account banao (5 min, NO CARD)
1. `pythonanywhere.com` → **Create a Beginner account**
2. Username + email + password → bas. Koi card, koi OTP nahi.

## Step 2: Code le aao (2 min)
1. Dashboard → **Consoles** → **Bash**
2. Type karo:
   ```
   git clone https://github.com/gurjeetsinghgill8-web/gil-clinic.git
   ```
   (Repo public hai — bina login ke chalega)

## Step 3: Virtualenv + dependencies (5-10 min)
```
cd ~/gil-clinic
mkvirtualenv gilclinic --python=python3.12
pip install -r requirements.txt
```
(pandas/numpy ke wheels aa jayenge — 5-10 min lagega, ek baar)

## Step 4: Web app banao (2 min)
1. **Web** tab → **Add a new web app** → **Next** → **Manual configuration** → Python 3.12 (jo latest ho)
2. Web tab mein ye set karo:
   - Source code: `/home/<username>/gil-clinic`
   - Working directory: `/home/<username>/gil-clinic`
   - Virtualenv: `/home/<username>/.virtualenvs/gilclinic`
   - **ASGI (beta)** option dikhe to chuno; ASGI application file: `/home/<username>/gil-clinic/pa_asgi.py`
   - Agar ASGI option nahi dikha: **WSGI configuration file** kholo aur ye 2 lines daalo:
     ```python
     import sys
     sys.path.insert(0, '/home/<username>/gil-clinic')
     from pa_asgi import application
     ```
     (PA par ASGI beta hai — reference: https://help.pythonanywhere.com/pages/ASGICommandLine)
3. **Reload** button dabao

## Step 5: .env banao (2 min)
**Files** tab → `/home/<username>/gil-clinic/.env` banao:
```
GROQ_API_KEY=<apne laptop ke .env se copy karo>
APP_BASE_URL=https://<username>.pythonanywhere.com
SUPER_ADMIN_PASSWORD=ApnaStrongPass123
CEO_PASSWORD=ApnaStrongPass456
SECRET_KEY=<koi bhi 40+ random characters>
GHOS_AI_KEYS_SECRET=<koi bhi 40+ random characters>
SYSTEM_AI_FALLBACK_ENABLED=false
```
→ **Web** tab → **Reload**
→ Browser: `https://<username>.pythonanywhere.com/health` → `{"status":"ok"}` dikhna chahiye ✅

## Step 6: Purana data migrate (optional)
- **Files** tab → Upload laptop ki `ghos_dev.db` → rename karke `ghos_prod.db` kar do
- (Pehle se `ghos_prod.db` bana hua ho to uski copy le lo)
- **Web** tab → **Reload**

## Step 7: Daily backup task (2 min)
- **Tasks** tab → scheduled task (daily):
  ```
  python /home/<username>/gil-clinic/backup_now.py
  ```
- Time: 23:30 UTC (Indian raat 5:00 AM). Free account = 1 task/day — kaafi hai
- Backups `backups/` folder mein 30 din tak rakhe jayenge, purane khud delete

## Step 8: API whitelist request (AI + WhatsApp ke liye — ek baar)
- Page: https://help.pythonanywhere.com/pages/RequestingAllowlistAdditions
- Ye domains request karo: `api.groq.com`, `graph.facebook.com`, `generativelanguage.googleapis.com`, `vision.googleapis.com`, `api.openai.com`, `api.anthropic.com`
- Approved hone tak AI features limited rahengi (baaki sab — queue, tokens, reports — normal chalega)

## WhatsApp Cloud API (optional — Meta free tier)
- `CLOUD_DEPLOY_GUIDE.md` Part 4 se Phone number ID + token le kar `.env` mein daalo:
  ```
  WHATSAPP_PHONE_NUMBER_ID=<id>
  WHATSAPP_ACCESS_TOKEN=<token>
  ```
- Whitelist approve hone ke baad messages seedha server se jayenge (koi popup nahi)

---

## Go-Live Checklist (PythonAnywhere)
- [ ] `/health` 200 OK dikh raha hai
- [ ] Admin login ho raha hai (SUPER_ADMIN_PASSWORD se)
- [ ] Patient register → tracking link `https://<username>.pythonanywhere.com/track/...` phone par ghar se khulta hai
- [ ] Backup task ka pehla run ho gaya (backups/ folder check)

**Laptop + Cloudflare Tunnel** abhi bhi chal raha hai — PA live hone tak dono saath chal sakte hain.
