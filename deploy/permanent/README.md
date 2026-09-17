# GIL CLINIC — app ko **permanent** aur **hamesha free** chalana

> ## 🟢 CARD NAHI HAI? — koi baat nahi, ye rasta bilkul bina card hai
>
> Oracle aur Google dono **card verification** maangte hain — is liye unka rasta **band** hai.
> Par **card ke bina bhi permanent solution hai**, aur wo actually **sabse safe** hai
> (data aapke hi computer par rehta hai, kisi cloud company ke paas nahi):
>
> ### 👉 Sirf ek file par DOUBLE-CLICK karein
> ```
> deploy\permanent\SETUP-NO-CARD.bat
> ```
> **Kaam kya karti hai (sab khud):**
> 1. Python install (agar nahi hai)
> 2. App ki files + dependencies setup
> 3. App ko **permanent server** banati hai — computer on hote hi chalu,
>    crash par auto-restart, aur **health watchdog** (app *hang* ho to bhi restart)
> 4. Internet par **permanent `https://` address** deti hai — **Tailscale** se
>    (free plan, **card nahi**, sirf ek baar Gmail/email se login)
> 5. Address screen par dikhati hai + browser khol deti hai
>
> **Aapko sirf itna karna hai:** double-click → 1 baar Tailscale me Gmail se login → bas.
> Uske baad aapka address hamesha same rahega, jaise `https://gilclinic-pc.tailXXXX.ts.net/opd/login`
> (PIN **5554** — Chief).
>
> **Ek hi limitation (imaandari se):** computer band = app band. Isliye clinic ka computer
> din me chalu rehna chahiye (power settings script khud theek kar deti hai — sleep off).
>
> **Agar aapke paas cloud wala rasta chahiye (computer band hone par bhi chale)** — uske liye
> card chahiye (Oracle/Google). Card mil jaye to neeche **STEP 1-6** follow karein, sab ready hai.

---

## Andar kya-kya hai (file list)

| File | Kaam |
|---|---|
| **`SETUP-NO-CARD.bat`** | **Ye chalayein** — pura setup ek click me (Python + server + permanent URL) |
| `install-windows-service.ps1` | App ko permanent server banana (auto-start, auto-restart, watchdog, firewall, sleep off) · `-DryRun` / `-Uninstall` |
| `windows-watchdog.ps1` | Har 3 min health check; app hang ho to restart |
| `install-permanent-url.ps1` | Permanent public HTTPS address · `-Provider tailscale\|ngrok\|cloudflare` · `-Status` |
| `bootstrap.sh` | (Cloud wala rasta) Oracle/Google/kisi bhi Ubuntu VM par 1-command install |
| `oracle-setup.bat` | (Cloud wala rasta) Oracle VM ke liye Windows one-click — **card chahiye** |
| `duckdns-update.sh` | Free permanent domain (DuckDNS) — VM ke liye |

---

# (Cloud rasta — sirf tab jab card ho) Oracle Always Free VM par 24/7

> **Kyun:** Oracle ka **Always Free** tier **kabhi expire nahi hota, kabhi sleep nahi karta** —
> 4 CPU + 24GB RAM + 200GB permanent disk, **hamesha ₹0**. Data VM ki permanent disk par
> rehta hai (Railway par har deploy me ud jata tha).

---

## Aapko sirf itna karna hai (5 kaam)

| # | Kaam | Kitna time | Kahan |
|---|---|---|---|
| 1 | Oracle account banana | 10 min | Browser |
| 2 | VM (computer) banana | 5 min | Oracle console |
| 3 | IP ko **Reserved** karna | 1 min | Oracle console |
| 4 | Port **80 + 443** kholna | 2 min | Oracle console |
| 5 | **`oracle-setup.bat` par double-click** | 8 min (khud chalta hai) | Aapka PC |

Uske baad aapka address ban jayega, jaise: **`https://152-67-12-34.sslip.io/opd/login`**

> ⚠️ **Domain ke liye kuch kharidna nahi hai.** `sslip.io` free + permanent hai (VM ke IP se
> apne aap ban jata hai). Chahein to baad me DuckDNS ka aasan naam bhi laga sakte hain
> (`deploy/permanent/duckdns-update.sh` se, wo bhi free).

---

## STEP 1 — Oracle account (10 min)

1. https://signup.cloud.oracle.com khol kar **Country: India** chuniye
2. Email + password → email verify
3. **Home Region: `India South (Hyderabad)`** chuniye (ya jo sabse paas ho) — ye baad me nahi badalta
4. Card details: **sirf verification ke liye** (₹0 charge hota hai, Always Free me kuch nahi katta).
   - Card reject hone lage to: dusra card try karein, ya seedha **Google Cloud e2-micro** (bhi always free) lein —
     wahan bhi wahi `oracle-setup.bat` chal jayega (bas username pooch lega, GCP me wo aapka email hota hai).
5. Account ban jaye to console: https://cloud.oracle.com

---

## STEP 2 — VM banana (5 min)

`Compute → Instances → Create instance` — in cheezon ko aise rakhein:

| Field | Kya chunein |
|---|---|
| Name | `gilclinic` |
| **Image** | **Ubuntu 22.04** (Canonical Ubuntu) |
| **Shape** | **`VM.Standard.A1.Flex`** (ARM, Always Free) — OCPU **2**, RAM **12 GB** |
| Networking | Default VCN (naya banaye ga to theek hai) |
| **Assign a public IPv4 address** | ✅ **Yes** (bahut zaroori) |
| **SSH keys** | **"Generate a key pair for me"** chunein → **private key download** kar lein |
| Boot volume | Default (50GB) — chahein to 100GB tak kar sakte hain (free) |

**Create** dabayein. 2-3 minute me **Running** ho jayegi.

### ⚠️ Agar "Out of capacity" error aaye (India region me common hai)
1. **Availability Domain** badal kar dobara try karein (AD-1 → AD-2 → AD-3)
2. Ya shape `VM.Standard.E2.1.Micro` (AMD, 1GB — Always Free, chhota par kaam kar jata hai)
3. Ya 5-10 minute baad try karein (capacity free hoti rehti hai)

---

## STEP 3 — IP ko Reserved karein (1 min, free)

Bina iske VM reboot hone par **IP badal sakta hai** aur patient ka link toot jayega.

`Networking → Reserved public IPs` → **Reserve public IP** → naam `gilclinic-ip` →
phir `Compute → Instances → gilclinic → Attached VNICs → ... → Public IP` me isi reserved IP ko assign karein.
(VM banate waqt hi "Reserved public IP" chunne ka option bhi milta hai — wo best hai.)

**Ye IP note kar lein**, jaise `152.67.12.34`.

---

## STEP 4 — Port 80 + 443 kholna (2 min)

`Networking → Virtual Cloud Networks → (aapka VCN) → Security Lists → Default Security List`
→ **Add Ingress Rules** — 2 baar:

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Save dabayein. VM ke andar ka firewall script khud khol leta hai — aapko kuch nahi karna.)

---

## STEP 5 — Sab kuch install: `oracle-setup.bat` par DOUBLE-CLICK

File yahan hai: **`deploy\permanent\oracle-setup.bat`**

Ye window 3 cheezein poochegi:
1. **VM ka Public IP** → STEP 3 wala IP paste karein
2. **SSH key** → ENTER dabayein (Downloads me jo `.key` file hai wo khud pakad lega), ya path dein
3. **username** → ENTER (Oracle me `ubuntu` hota hai)

Ab 5-8 minute ruk jaayein — ye window khud ye sab kar degi:

| # | Ye khud karta hai | Fayda |
|---|---|---|
| 1 | VM se connect + naya code GitHub se | Aapka latest app |
| 2 | Python + dependencies install | — |
| 3 | **Data permanent disk par** (`/opt/gilclinic/data`) | Data kabhi nahi udta |
| 4 | App ko **systemd service** banana | VM restart/bijli jane par bhi app wapas chalu |
| 5 | **Crash par auto-restart** (999 baar) | App gir jaye to 5 second me wapas |
| 6 | **Health watchdog (har 2 min)** | App **hang** ho jaye to bhi restart |
| 7 | **HTTPS (Caddy + Let's Encrypt)** apne aap | `https://…sslip.io` — secure lock |
| 8 | **Roz 2 baar backup** (13:00, 21:00) + 30 din tak rakhta hai | Galti se kharab data wapas |
| 9 | VM ka firewall khud khol deta hai | Bahar se access |
| 10 | Aapka **address** set + health check | Link kaam karta hai |
| 11 | `gilclinic-update` command | Aage naya code = ek command |

Aakhir me screen par aapka address aa jayega + browser khul jayega.

---

## STEP 6 — Test (phone se, 2 min)

1. Address kholiye: `https://<aapka-address>/opd/login` → PIN **5554** (Chief)
2. Kisi patient ko select karke **📱 Patient link** dabayein → WhatsApp par bhej dein
3. Patient ke phone par link khulega → mobile number verify → BP/sugar bharega → graph banega
4. Patient **📄 PDF download** kar sakta hai, aur **🩺 Doctor ko bhejo** se kisi bhi doctor ko
   read-only link bhej sakta hai

Bas! Ab app **24/7 chalu hai, hamesha free**.

---

## Rozmarra (sirf zaroorat pade to)

VM par SSH karke (ya `oracle-setup.bat` dobara chala kar) ye commands:

| Kaam | Command |
|---|---|
| App chalu hai ya nahi | `sudo systemctl status gilclinic` |
| App restart | `sudo systemctl restart gilclinic` |
| Logs dekhna | `sudo journalctl -u gilclinic -n 80 --no-pager` |
| **Naya update** (GitHub se) | `sudo gilclinic-update` |
| Backup dekhein | `ls /opt/gilclinic/data/backups` |
| Health check | `curl -s localhost:8000/health` |

---

## Kuch galat ho to (troubleshooting)

| Problem | Wajah | Ilaaj |
|---|---|---|
| Browser me "site can't be reached" | Port 80/443 cloud me khule nahi | STEP 4 dobara karein |
| HTTPS certificate ka error | Certificate ban raha hota hai | 2-3 minute ruk kar refresh karein |
| `setup.bat` me SSH fail | IP ya key galat / VM abhi Running nahi | IP dobara copy karein, 2 min baad try karein |
| "Out of capacity" VM banate waqt | ARM capacity full | Dusra Availability Domain, ya `E2.1.Micro` |
| App chalu par health fail | Code/DB issue | `sudo journalctl -u gilclinic -n 80` ka output bhej dein |
| Patient ka link purane address par ja raha hai | `APP_BASE_URL` purana hai | Naya install khud set karta hai; phir bhi `sudo nano /opt/gilclinic/.env` me `APP_BASE_URL` dekh lein |

**Kuch bhi atak jaye:** jo bhi screen par likha ho, wo copy karke bhej dein — main dekh lunga.

---

## Off-site backup (optional, 2 min — sabse safe)

VM hi kharab ho jaye to bhi data bachane ke liye (private GitHub repo me rozana backup):

1. GitHub par **private** repo banayein: `gil-clinic-backup`
2. VM par: `ssh-keygen -t ed25519 -f ~/.ssh/backup -N ""` → `cat ~/.ssh/backup.pub` copy
3. Us repo me `Settings → Deploy keys → Add deploy key` (✅ Allow write access) me paste
4. `sudo bash deploy/permanent/bootstrap.sh --auto-domain --backup-repo git@github.com:gurjeetsinghgill8-web/gil-clinic-backup.git`

---

## Aur ek rasta (agar Oracle me card reject ho jaye)

**Google Cloud e2-micro** (Always Free): 1 vCPU + 1GB RAM + 30GB disk, US region, kabhi expire nahi.
Steps ekdum same hain — VM bana kar wahi **`oracle-setup.bat`** chalayein (username me apna GCP username dein).
Deploy ke waqt `--auto-domain` ki jagah GCP ke external IP se bhi wahi `sslip.io` address ban jayega.

**Ya bilkul bina cloud (₹0, aaj hi):** clinic ka PC hi server —
`powershell -ExecutionPolicy Bypass -File deploy\permanent\install-windows-service.ps1`
(boot par auto-start + crash par auto-restart + health watchdog + tunnel auto-start).
Sirf kami: computer band = app band.
