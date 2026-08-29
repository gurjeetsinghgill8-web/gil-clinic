# GIL CLINIC — Cloud Deploy Guide (Oracle Always Free) + Cloudflare Tunnel + WhatsApp Cloud API
## 29-Aug-2026 · हिंदी step-by-step · पूरा cost ₹0/माह (data permanent)

---

## PART 1 — Oracle Cloud Always Free (24/7, कभी sleep नहीं)

### Step 0: अपना code GitHub पर push करें (एक बार, 5 मिनट)
Oracle VM पर deploy script आपके repo से code clone करता है, इसलिए नई fixes GitHub पर होनी चाहिए:
1. [GitHub Desktop](https://desktop.github.com/) install करें (अगर नहीं है) → **File → Add local repository** → यह project folder चुनें
2. Changes list में सब files दिखेंगी → नीचे **Summary** लिखें (जैसे "AI BYOK + queue fixes") → **Commit to main**
3. **Push origin** दबाएँ → GitHub login (अपना account)
4. Verify: `github.com/gurjeetsinghgill8-web/gil-clinic` पर नई commit दिखे
5. ध्यान: `.env`, `*.db`, `secret.txt` **gitignore में हैं — patient data/keys push नहीं होंगे** (सुरक्षित)

### Step 1: Oracle Account बनाएँ (एक बार, ~15 मिनट)
1. `cloud.oracle.com` → **Start for free** → signup form (credit/debit card सिर्फ verification — charge ₹0)
2. India में कुछ cards reject होते हैं — तो दूसरा card try करें। **Reject हो जाए तो Part 4 (Google e2-micro)** use करें
3. Login के बाद: **Menu → Compute → Instances → Create instance**
   - Name: `gil-clinic`
   - Image: **Ubuntu 22.04** (Canonical)
   - Shape: **VM.Standard.A1.Flex** (ARM, 2 OCPU + 12GB RAM — free limit के अंदर)
   - **SSH keys**: "Generate a key pair for me" → दोनों keys download करके save करें
   - **Boot volume: 100 GB** (Always Free में 200GB तक मुफ्त)
4. **Create** → 1-2 मिनट में instance "Running"

### Step 2: Port 8000 खोलें (ज़रूरी!)
1. Instance page → **Virtual cloud network** लिंक → **Security Lists** → Default list → **Add Ingress Rules**
2. Source CIDR `0.0.0.0/0`, Protocol **TCP**, Destination Port **8000** → Save

### Step 3: Deploy (5 मिनट)

**⭐ Easy way (recommended — एक ही command, sab automatic):**
1. Downloaded private key ko project folder mein `gil-clinic-key.key` नाम से save करें
2. Laptop par (PowerShell):
   ```
   .\deploy_remote.ps1 -VmIp <VM-PUBLIC-IP> -KeyPath .\gil-clinic-key.key
   ```
   Script खुद: SSH test → `deploy_oracle.sh` upload + चलाना → health check → admin credentials laptop पर save
3. Browser में खोलें: `http://<VM-PUBLIC-IP>:8000` ✅
4. **Existing patient data migrate karna ho (laptop ka data VM par):**
   ```
   .\deploy_remote.ps1 -VmIp <VM-PUBLIC-IP> -KeyPath .\gil-clinic-key.key -Mode PushData
   ```
   (VM ka purana data pehle `pre-migrate-*.db` backup ban jata hai, phir local `ghos_dev.db` VM par chala jata hai)
5. **Backup laptop par** (हफ्ते में एक बार): `.\deploy_remote.ps1 -VmIp <VM-PUBLIC-IP> -KeyPath .\gil-clinic-key.key -Mode PullBackup`
6. **VM ki halat dekhni ho**: `-Mode Status` (service/data/backups/disk sab ek saath)

**Manual way (backup):**
1. अपने laptop पर: downloaded private key को `gil-clinic-key.key` नाम से save करें
2. SSH करें:
   ```
   ssh -i gil-clinic-key.key ubuntu@<VM-PUBLIC-IP>
   ```
3. VM पर: मेरी बनाई script चलाएँ (यह project में है — पहले laptop से VM पर copy करें):
   ```
   # laptop se:
   scp -i gil-clinic-key.key deploy_oracle.sh ubuntu@<VM-PUBLIC-IP>:~/
   # VM par:
   sudo bash ~/deploy_oracle.sh
   ```
   Script खुद: Docker install → app clone → **permanent data folder** `/opt/gilclinic/data` → systemd (auto-restart + boot-start) → **रोज़ 2 बार backup cron** → firewall note
4. Browser में खोलें: `http://<VM-PUBLIC-IP>:8000` ✅
5. **Password बदलें:** `sudo nano /opt/gilclinic/.env` → `SUPER_ADMIN_PASSWORD` और `CEO_PASSWORD` अपना डालें → `sudo systemctl restart gilclinic`

### Step 4: Data safety (automatic)
- Data file: `/opt/gilclinic/data/ghos_prod.db` — **permanent disk पर, redeploy/reboot पर कभी नहीं मिटता**
- हर boot से पहले + रोज़ 2 बार backup → `/opt/gilclinic/data/backups/`
- Extra safety (recommended): हफ्ते में एक बार laptop पर खींचें:
  ```
  scp -i gil-clinic-key.key ubuntu@<VM-PUBLIC-IP>:/opt/gilclinic/data/backups/daily-*.db ./
  ```
- Oracle की चेतावनी: VM **7 दिन पूरी तरह idle** रहे तो Oracle reclaim कर सकता है — clinic app रोज़ चलेगा तो कोई issue नहीं, फिर भी backups की आदत रखें

---

## PART 2 — Google Cloud e2-micro (Oracle reject हो तो)

1. `console.cloud.google.com` → signup (card verification, no charge) → **Compute Engine → VM instances → Create**
2. Region: `us-central1`, Machine type: **e2-micro** (Always Free), Boot disk: **Ubuntu 22.04, 30GB standard**
3. Firewall: "Allow HTTP traffic" checkbox + VM बनने के बाद:
   ```
   gcloud compute firewall-rules create gil8000 --allow tcp:8000
   ```
4. SSH → वही `deploy_oracle.sh` चलाएँ (यह Google पर भी चलता है)

---

## PART 3 — Cloudflare Tunnel (patients घर से भी link खोलें, ₹0)

**Quick start (pehle se ready):** `START_TUNNEL.bat` double-click करें — tunnel खुद चलेगा,
trycloudflare.com URL `.env` के `APP_BASE_URL` में खुद set हो जाएगा (server restart की ज़रूरत नहीं)।
Patient tracking links उसी public URL से जाएँगी। `cloudflared.exe` पहले से project folder में है।

Quick tunnel का URL हर restart पर बदलता है — permanent ke liye neeche steps:

VM/laptop के port 8000 को बिना IP खोले public HTTPS URL देना हो तो:

1. Laptop या VM पर: [cloudflared download](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. Quick tunnel (testing, URL हर बार बदलता है):
   ```
   cloudflared tunnel --url http://localhost:8000
   ```
   → मिलेगा `https://xxxx.trycloudflare.com` — patient को यही भेजें
3. **Permanent URL** (recommended): सस्ता domain (~₹800/साल, Namecheap) → [Cloudflare free account](https://dash.cloudflare.com) में add → tunnel को domain से जोड़ें:
   ```
   cloudflared tunnel login
   cloudflared tunnel create gilclinic
   cloudflared tunnel route dns gilclinic clinic.aapkadomain.com
   cloudflared tunnel run gilclinic
   ```
   (systemd service बना दें तो हमेशा चलेगा)
4. App में `APP_BASE_URL=https://clinic.aapkadomain.com` कर दें (`.env` में) — तब WhatsApp tracking links patient के फोन पर घर से खुलेंगे

---

## PART 4 — WhatsApp Cloud API (Meta) — बिना popup के direct messages (₹0)

अभी messages receptionist/technician के browser से wa.me popup से जाते हैं। **Direct auto-send** के लिए Meta का free API:

1. `developers.facebook.com` → **Create App** → type "Business" → app बनाएँ
2. App Dashboard → **WhatsApp → Set up** → Test number मिलेगा (अपना नंबर add करें, OTP से verify)
3. **API Setup** panel से दो चीज़ें copy करें:
   - `Phone number ID`
   - `Permanent access token`
4. App के `.env` में डालें (VM/laptop):
   ```
   WHATSAPP_PHONE_NUMBER_ID=<Phone number ID>
   WHATSAPP_ACCESS_TOKEN=<token>
   ```
   → restart server
5. अब registration + call/recall पर message **सीधे server से patient को भेजा जाएगा** — किसी browser popup की ज़रूरत नहीं
6. **Free limits (Meta):** test number से सिर्फ verified numbers को messages जाते हैं — असली patients को भेजने के लिए Meta Business verification (free) + अपना business number जोड़ें; 1000 free conversations/माह तक मिलते हैं (उसके बाद ~₹0.5-1/msg — clinic का खर्च, हमारा ₹0)

### SMS fallback (optional)
`utils/sms.py` में provider env (`MSG91_AUTH_KEY` वगैरह) डालकर SMS भी चालू किया जा सकता है — ज़रूरत पड़े तो next round में wire कर दूँगा।

---

## PART 5 — Go-Live Checklist

- [ ] Oracle/Google VM चल रहा, `http://<IP>:8000` खुलता है
- [ ] Port 8000 firewall में open
- [ ] `SUPER_ADMIN_PASSWORD`/`CEO_PASSWORD` बदले (`.env`)
- [ ] `GHOS_AI_KEYS_SECRET` set (first deploy से पहले — बाद में बदला तो पुरानी clinic keys unreadable)
- [ ] 1-2 हफ्ते clinics के migrate होने के बाद `SYSTEM_AI_FALLBACK_ENABLED=false` → हमारी AI bills शून्य
- [ ] Backup folder में `daily-*.db` files बन रही हैं (कम से कम एक बार check करें)
- [ ] Patient tracking link clinic के बाहर से भी खुलता है (Tunnel/domain से)
