# GIL CLINIC — FREE Hosting Plan (Deep Research, 29-Aug-2026)
## "Paisa nahi dena + App kabhi band na ho + Data kabhi na ude"

---

## 0. TL;DR (सीधी बात)

| | Option | Cost | Card चाहिए? | App सोता है? | Data safe? | Effort |
|---|---|---|---|---|---|---|
| ⭐ 1 | **अपना Laptop/PC = server** (आज ही शुरू) | ₹0 | ❌ नहीं | ❌ नहीं (जब तक computer on) | ✅ हाँ — आपकी disk पर + auto-backup | 5 मिनट (double-click) |
| ⭐ 2 | **Oracle Cloud Always Free** (हमेशा free cloud VM) | ₹0 हमेशा | ✅ signup verification के लिए | ❌ कभी नहीं | ✅ हाँ — 200GB permanent disk | 1 घंटा (guide नीचे) |
| 3 | Google Cloud e2-micro (always free) | ₹0 | ✅ | ❌ नहीं | ✅ (10GB disk) | 1 घंटा |
| 4 | Render free + keep-alive ping | ₹0 | ❌ नहीं | ⚠️ ping से जगाते हैं | ⚠️ DB 30 दिन में expire! | 30 मिनट — **recommended नहीं** |
| 5 | PythonAnywhere free | ₹0 | ❌ नहीं | ❌ नहीं | ✅ file system permanent | Medium (AI APIs के लिए whitelist चाहिए) |

**Best path:** पहले **Option 1 (laptop)** आज चालू करो — data तुरंत safe। फिर हफ्ते भर में **Option 2 (Oracle)** पर shift करो — तब laptop बंद हो तो भी app 24/7 चलेगा, हमेशा free।

**Railway क्यों छोड़ना सही है:** Railway का free tier 2023 में ही खत्म हो गया; अब सिर्फ $5 hobby plan है ([Kuberns — Railway Free Tier 2026](https://kuberns.com/blogs/railway-free-tier/), [agentdeals — Railway 2026 caution](https://agentdeals.dev/vendor/railway))। और Railway पर बिना paid volume के SQLite data हर redeploy पर मिट जाता है — **इसीलिए आपका data "save nahin hota" था।**

---

## 1. OPTION 1 — Laptop/PC Server (आज ही, 5 मिनट, ₹0)

आपने सही सोचा था: **"laptop mein hi server ho jaaye"** — यह पूरी तरह possible है और data का सबसे safe तरीका है (data आपकी अपनी disk पर)।

### Step-by-step
1. **`START_LOCAL.bat` पर double-click** करें (मैंने बना दिया है) — यह खुद:
   - Python check करता है, पहली बार dependencies install करता है
   - **शुरू होने से पहले auto-backup** लेता है (`backups/` folder में)
   - LAN IP दिखाता है और browser खोलता है
2. Clinic के दूसरे computers/phones पर खोलें: `http://<laptop-ka-IP>:8000` (दोनों same WiFi पर हों)
3. **Windows Firewall popup आए तो "Allow access"** दबाएँ (यही LAN access खोलता है)
4. Laptop sleep न हो: Settings → System → Power → Screen and sleep → **Never**
5. दिन में एक बार (या server बंद करते वक्त) **`BACKUP_DATA.bat`** double-click — extra safe। OneDrive/Google Drive में mirror करने का option उसमें लिखा है।

### Patient को link कैसे पहुँचेगा?
- Tracking link अब **auto-detect** होता है — जिस address से staff ने खोला (LAN IP), उसी से patient का link बनता है ✅ (मैंने fix किया है)
- Patient का phone same WiFi पर हो तो direct खुलेगा
- **घर बैठे patient** के लिए बाहर से access चाहिए तो नीचे §3 (Cloudflare Tunnel, ₹0) — 10 मिनट

### कमियाँ (ईमानदारी से)
- Laptop बंद = server बंद (इसीलिए Oracle next step है)
- बिजली चली जाए तो data loss का risk — इसीलिए auto-backup हर start पर + BACKUP_DATA.bat
- Internet धीमा हो तो clinic के अंदर कोई फर्क नहीं (LAN), सिर्फ बाहर वालों को slow

---

## 2. OPTION 2 — Oracle Cloud Always Free (सबसे best free cloud, 2026 में भी live)

Oracle का "Always Free" tier अभी भी मौजूद है — **हमेशा free, कभी expire नहीं होता, कभी sleep नहीं करता** ([2026 setup guide](https://shicheng-guo.github.io/tutorials/2026/06/06/oracle-cloud-free-tier), [HostDir review](https://hostdir.net/providers/oracle-cloud-free-tier)):

- **ARM VM: 4 CPU + 24GB RAM + 200GB permanent disk** — आपके FastAPI app के लिए overkill 😄
- या 2 छोटे AMD VMs (1GB RAM each) — काफी है
- Free में PostgreSQL भी (Always Free DB) या VM की disk पर SQLite + volume
- **कोई sleep नहीं, कोई monthly bill नहीं** — जब तक resources limits के अंदर रहो

### ध्यान देने वाली बातें (जो reviews बताते हैं)
- **Signup में credit/debit card मांगता है** (सिर्फ verification — charge नहीं होता)। कुछ Indian cards reject हो जाते हैं — तो दूसरा card try करें या Google Cloud e2-micro
- "Hidden costs" review ([space-node.net](https://space-node.net/blog/oracle-vps-free-tier-review-2026)): अगर VM **लगातार 7 दिन idle** रहे तो Oracle उसे reclaim कर सकता है — हमारा clinic app रोज़ use होगा, idle नहीं होगा। Phir bhi **रोज़ का auto-backup** ज़रूर रखें (backup_now.py को cron में डालेंगे)
- Setup में Docker + Railway जैसा one-click नहीं — मैं next round में **step-by-step deploy script + guide** बनाऊँगा (ssh, docker-compose, volume mount, systemd)

### Deploy plan (मैं बनाऊँगा, Lego Block 4)
1. Oracle VM create (Ubuntu 22.04 ARM/AMD)
2. `deploy_oracle.sh` — app clone + Docker build + SQLite volume mount
3. systemd service — auto-restart, boot पर auto-start (कभी बंद नहीं)
4. `backup_now.py` cron — रोज़ 2 बार backup + scp to laptop
5. APP_BASE_URL env = VM का public IP/domain

---

## 3. OPTION 3 — Google Cloud e2-micro (backup option)

Google का **e2-micro Always Free** ([free tiers 2026](https://agentdeals.dev/hosting-pricing)): 1GB RAM + 30GB disk, US region, कभी expire नहीं। Oracle reject करे तो यह use करें। Setup Oracle जैसा ही (VM + Docker + systemd)। Card चाहिए (no charge)।

## 4. बाकी options — क्यों नहीं (short verdict)

| Option | क्यों नहीं |
|---|---|
| Render free | App 15 min बाद **सो जाता है**; free Postgres **30 दिन में मिट जाता है** — patient data के लिए खतरनाक। UptimeRobot ping से जगाया जा सकता है पर DB expire वाला risk रहता है |
| HuggingFace Spaces | Free Docker मिलता है पर **persistent storage paid है** → data उड़ेगा |
| Vercel/Netlify/Cloudflare Workers | Python FastAPI full app नहीं चलता (serverless functions अलग model है) |
| Koyeb free | 1 service free, पर free tier में persistent volume नहीं → SQLite उड़ेगा |
| PythonAnywhere free | बिना card ✅, filesystem permanent ✅, पर AI provider APIs (Groq/OpenAI) के लिए **outbound whitelist request** भरनी पड़ती है और free CPU limited है। Fallback के तौर पर ठीक |
| Fly.io | Free allowance है पर card चाहिए और usage-based bills का risk |

## 5. बाहर से access (patients घर से) — Cloudflare Tunnel, ₹0

Laptop/Oracle दोनों पर free public HTTPS URL पाने के लिए **Cloudflare Tunnel** — बिना card, बिना port forwarding ([cfld — persistent tunnel tool](https://github.com/cliftonc/cfld), [Tunnel guide](https://github.com/HeyPuter/puter/blob/main/README.md)):
- Quick tunnel: `cloudflared tunnel --url http://localhost:8000` → random `https://xxx.trycloudflare.com` मिलता है (हर restart पर बदलता है — testing के लिए)
- Permanent URL: ₹800-900/साल का सस्ता domain (Namecheap) + free Cloudflare account → `clinic.aapkadomain.com` हमेशा same
- यह भी Lego Block में जोड़ूँगा (script + guide)

---

## 6. Action Plan (आज → इस हफ्ते)

| दिन | काम |
|---|---|
| **आज** | Laptop पर `START_LOCAL.bat` चलाएँ → clinic ke staff `http://<LAN-IP>:8000` से चलाएँ → शाम को `BACKUP_DATA.bat` |
| **कल** | मैं interconnection bugs के बाकी fixes करूँगा (Lego Blocks) |
| **2-3 दिन में** | Oracle signup try करें (card चाहिए); reject हुआ तो Google e2-micro |
| **हफ्ते में** | मैं deploy script + Cloudflare Tunnel guide बनाऊँगा → 24/7 free hosting, data volume पर permanent |

**Sources:** [Railway Free Tier 2026](https://kuberns.com/blogs/railway-free-tier/) · [Hosting Free Tier Comparison 2026](https://agentdeals.dev/hosting-free-tier-comparison-2026) · [Oracle Always Free 2026 Guide](https://shicheng-guo.github.io/tutorials/2026/06/06/oracle-cloud-free-tier) · [Oracle Free Tier Review](https://space-node.net/blog/oracle-vps-free-tier-review-2026) · [FastAPI Hosting Compared 2026](https://granite.so/hosting/fastapi) · [Cloudflare Tunnel](https://github.com/cliftonc/cfld) · [free-for-dev list](https://github.com/ripienaar/free-for-dev)
