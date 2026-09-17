# GIL CLINIC — Permanent FREE Hosting (Railway band ho gayi, uska pakka ilaaj)

> **17-Sep-2026 · Status:** Railway service `gil-clinic` **Offline** hai (free tier 2023 me hi khatam — ab
> sirf $5/month Hobby plan hai). Isliye ab app **hamesha-free** jagah chalti hai:
> **apna computer (turant)** + **Oracle Cloud Always Free VM (24/7, permanent)**.

---

## 0. TL;DR — 2 minute me faisla

| | Kya | Kharcha | Kab band hota hai | Kab chalu karein |
|---|---|---|---|---|
| **A** | **Clinic ka computer hi server** (`install-windows-service.ps1`) | ₹0 | Jab computer band ho | **Aaj hi** (5 min) — clinic ke andar 100% chalta hai |
| **B** | **Oracle Cloud Always Free VM** (`deploy/permanent/bootstrap.sh`) | ₹0 **hamesha** | Kabhi nahi (24/7, no sleep, 200GB disk) | Is hafte (signup me card verification lagta hai) |
| C | Google Cloud e2-micro (always free) | ₹0 | Kabhi nahi | B backup ke liye |
| ❌ | Railway / Render free / Koyeb free / HuggingFace | — | Free tier khatam / app sota hai / data udta hai | **Nahi** |

**Sabse achha rasta:** pehle **A** se aaj clinic chalu karo (data turant safe, clinic ke andar koi rukawat nahi),
phir **B** par shift ho jao — uske baad computer band hone par bhi app 24/7 chalta rahega, aur **paisa zindagi bhar ₹0**.

---

## A. Aaj hi: clinic ka computer = permanent server (₹0)

```powershell
# PowerShell **Administrator** me:
powershell -ExecutionPolicy Bypass -File deploy\permanent\install-windows-service.ps1
```

Ye kya karta hai (sab apne aap, dobara chalane par bhi safe):

| # | Kaam | Fayda |
|---|---|---|
| 1 | **GILCLINIC-Server** task (boot par start) | Computer on hote hi app chalu — koi click nahi |
| 2 | **Restart 999 baar / 1 minute** | App crash ho to Windows khud wapas chalu kar de |
| 3 | **GILCLINIC-Tunnel** task | Public patient link (Cloudflare tunnel) bhi auto-start |
| 4 | **GILCLINIC-Watchdog** (har 3 min) | App **hang** ho jaye (crash na ho) to bhi restart — ye asli "app band ho gayi" ka ilaaj |
| 5 | Firewall + power settings | Clinic ke phone/PC se access + laptop sleep nahi |

**Clinic ke andar:** `http://<is-PC-ka-IP>:8000/opd/login` · **Patient link:** tunnel log me URL
(`Get-Content scratch\service-logs\tunnel.log | Select-String trycloudflare`).

Band karna ho: `... -Uninstall`

⚠️ **Sirf ek limitation:** computer band = app band. 24/7 ke liye neeche **B** karein.

---

## B. Is hafte: Oracle Cloud **Always Free** VM (24/7, hamesha ₹0)

Oracle ka Always Free tier **kabhi expire nahi hota, kabhi sleep nahi karta**:
**4 CPU + 24GB RAM + 200GB permanent disk** — clinic app ke liye bahut zyada. Signup me card sirf
**verification** ke liye lagta hai (charge nahi hota); kuch Indian cards reject ho jate hain — tab **C** (Google) try karein.

### B1. VM banana (Oracle console, 10 minute)
1. https://cloud.oracle.com → sign up (Always Free chuno)
2. **Compute → Instances → Create instance**
   - Image: **Ubuntu 22.04** (ya 24.04)
   - Shape: **VM.Standard.A1.Flex** (ARM, Always Free) — 2 OCPU / 12GB kaafi hai
   - **Add SSH key** (apni public key paste karein — Windows me `ssh-keygen -t ed25519`)
3. Create hone ke baad **Public IP copy** karein → **Reserved IP** bana dein
   (Networking → Reserved public IPs → Assign) — free hai, aur IP kabhi nahi badlega
4. **Security List / NSG** me **port 80 + 443** open karein (Ingress rule: 0.0.0.0/0, TCP, 80,443)

### B2. Free permanent domain (2 minute, ₹0)
- **DuckDNS** (recommended): https://www.duckdns.org → Google/GitHub se login → naam chuno, e.g. `gilclinic`
  → token copy. (Bina card, hamesha free.)
- Ya **sslip.io**: koi signup nahi — aapka host `152-67-12-34.sslip.io` jaisa hi kaam karta hai
  (IP ko dash se likhein). Certificate Caddy khud le lega.

### B3. VM par 2 command (bas itna hi)
```bash
# VM me SSH karke:
git clone https://github.com/gurjeetsinghgill8-web/gil-clinic.git /tmp/gc && cd /tmp/gc

# DuckDNS domain + token ke saath (ek hi command — sab kuch set ho jata hai)
sudo bash deploy/permanent/bootstrap.sh --domain gilclinic.duckdns.org
```
(DuckDNS use kar rahe hain to pehle: `sudo bash deploy/permanent/duckdns-update.sh --domain gilclinic --token <TOKEN> --install`)

**Bas. Ab app 24/7 chalu hai:** `https://gilclinic.duckdns.org/opd/login`

### B4. Bootstrap kya-kya karta hai
| # | Kaam | Kyun zaroori |
|---|---|---|
| 1 | Data **permanent disk** par (`/opt/gilclinic/data`) | Railway par SQLite har redeploy me ud jata tha — ab kabhi nahi |
| 2 | `systemctl` service + boot par auto-start | VM restart/bijli jane par bhi app wapas chalu |
| 3 | `Restart=always` + crash-loop guard | App crash ho to 5 sec me wapas (aur bekaar loop se bachav) |
| 4 | **Health watchdog** (har 2 min `/health`) | App **hang** ho to bhi apne aap restart — "app band" ka pakka ilaaj |
| 5 | **Caddy + Let's Encrypt HTTPS** | Free SSL, koi renew ka jhanjhat nahi |
| 6 | **Roz 2 baar backup** (13:00 + 21:00) + 30 din retention | Galti se data kharab ho to wapas |
| 7 | **Off-site backup** (optional private GitHub repo) | VM hi ud jaye (Oracle account issue) to bhi data safe |
| 8 | `gilclinic-update` command | Naya code deploy = ek command |
| 9 | `APP_BASE_URL` = aapka domain | Patient link **hamesha** sahi URL ka |
| 10 | Heartbeat cron | Oracle "idle VM" samajh kar reclaim na kare |

**Off-site backup chalu karne ke liye** (recommended — 30 second):
1. GitHub par ek **private** repo banayein, e.g. `gil-clinic-backup`
2. VM par ek deploy key banayein: `ssh-keygen -t ed25519 -f ~/.ssh/backup -N ""` aur public key us repo me
   **Deploy keys → Allow write access** ke saath add karein
3. `sudo bash deploy/permanent/bootstrap.sh --domain <domain> --backup-repo git@github.com:gurjeetsinghgill8-web/gil-clinic-backup.git`

### B5. Rozana/zaroorat par
```bash
sudo gilclinic-update                  # naya code deploy (git pull + deps + restart + health check)
systemctl status gilclinic             # app chalu hai?
journalctl -u gilclinic -n 80 --no-pager   # logs
curl -s localhost:8000/health          # health
ls /opt/gilclinic/data/backups         # backups
```

---

## C. Backup option: Google Cloud e2-micro (always free)
Oracle signup reject ho jaye to yahi karein — steps ekdum same hain (Ubuntu VM + `bootstrap.sh --domain ...`).
Free tier: 1 vCPU + 1GB RAM + 30GB disk, US region, kabhi expire nahi.

---

## D. Railway ka kya karein?

- **Abhi ke liye:** use na karein. Free tier nahi hai, aur bina paid volume ke SQLite data har deploy me udta hai —
  aapka "data save nahi hota" wala issue isi wajah se tha.
- **Agar kabhi paid plan lein** (ya staging ke liye use karein): repo me `railway.json` add kar diya gaya hai
  (healthcheck `/health`, restart policy, aur DB ko **volume** par rakhne ka rasta `RAILWAY_VOLUME_MOUNT_PATH` se) —
  phir Railway par bhi data safe rahega.
- **Project delete mat karein** — offline pada rehne do, kuch kharcha nahi karta.

---

## E. Ek zaroori bug jo is baar pakda gaya (permanent fix ho gaya)

`.env` me `APP_BASE_URL` **purana tunnel/Railway URL** pada reh gaya tha
(`https://rio-minerals-rim-skills.trycloudflare.com`) — aur tunnel band hone ke baad bhi app **wahi** base URL
patient links me bhej raha tha → patient ke phone par "site not found".

Ab `src/utils/public_url.py` har baar check karta hai:
1. `APP_BASE_URL` set hai **aur uska DNS zinda hai** → wahi use karo
2. Host mar chuka hai (tunnel/Railway band) → usko 5 minute ke liye "dead" mark karo aur
   **request ke apne host** se link banao (jo abhi chal raha hai)
3. `Patient Monitor` tab par doctor ko **warning** dikhti hai: kaun sa URL use ho raha hai aur kyun

Isliye ab patient link kabhi chup-chaap toota hua nahi jayega — doctor ko screen par hi pata chal jayega.

---

## F. Aaj ka action plan (checklist)

- [ ] **Aaj:** `install-windows-service.ps1` chala kar clinic ka computer server bana lein (5 min)
- [ ] **Aaj:** ek patient ko apna link bhej kar phone par test karein (verify → reading → graph → PDF)
- [ ] **Is hafte:** Oracle (ya Google) VM banayein + `bootstrap.sh` chalayein → 24/7 free
- [ ] **Is hafte:** DuckDNS free domain + `--backup-repo` (off-site backup) chalu karein
- [ ] **Uske baad:** purane tunnel wale `.env` ki fikar khatam — `APP_BASE_URL` ab permanent domain hoga
