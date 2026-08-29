# GIL CLINIC — System Status Report + Lego Fix Plan
## 29-Aug-2026 · "हर cheez आपस में जुड़ी हो — sabko sab pata ho"

---

## 1. Diagnosis — आपकी शिकायतों की असली जड़ें (code पढ़कर मिली)

### समस्या 1: "Patient ko message nahi jata / waiting nahi pata"
| # | Root cause (code में मिला) | File |
|---|---|---|
| 1 | Patient के WhatsApp message से **tracking link जानबूझकर हटाया गया था** — "tracking_url accepted but NOT used" | `whatsapp_cloud_api.py` ✅ **FIXED** |
| 2 | Message सिर्फ receptionist के browser से **wa.me link auto-open** होने पर जाता है — popup block हुआ तो patient को कुछ नहीं मिलता | `reception.html` — Block 2 में auto-send |
| 3 | Tracking link **dead Railway URL** से बनता था (`cardioqueue-production.up.railway.app` hardcoded default) — Railway बंद = link मरा हुआ | `staff_routes.py` ✅ **FIXED** (अब Host auto-detect) |

### समस्या 2: "Receptionist add kare to TMT wale ko nahi milta"
| # | Root cause | Status |
|---|---|---|
| 1 | Queue entry का `department` field **सब services के लिए "Cardiology" hardcoded** है; department pages `service_code` filter से चलते हैं (TMT/ECG/Echo) — fragile | Block 3 में ठीक करूँगा: हर service का सही department लिखा जाए |
| 2 | Department pages auto-refresh पर depend हैं — नया patient आया तो technician को refresh करना पड़ता है | Block 3: 15-second live polling + sound alert |
| 3 | Registration → TMT तक **कोई instant notification नहीं** (कोई sound/दृश्य alert नहीं) | Block 3 |

### समस्या 3: "TMT wala call kare to patient nahi aata"
- Call action patient को सिर्फ **wa.me manual link** से जाता है (receptionist/technician के browser से) — patient के पास कोई live alert नहीं पहुँचता
- Fix plan (Block 4): tracking page पर **live "आपका token बुलाया गया" banner + sound** + call पर automatic WhatsApp (Cloud API env दें तो direct auto-send, वरना wa.me popup)

### समस्या 4: "Doctor/receptionist/dietician sab disconnected"
- Doctor (OPD) अपने अलग system में है (`/opd/`), staff dashboard अलग (`/staff/`), queue engine अलग (`/api/v1/queue/`)
- तीनों एक ही DB पर हैं, पर **कोई shared live status board नहीं** जो सबको एक साथ दिखाए
- Fix plan (Block 5): एक **"Clinic Live Board"** page — reception→waiting→called→in-progress→completed→report-ready की पूरी pipeline हर role को दिखे + OPD doctor को "patient ready" alert

### समस्या 5: "App chalu nahi ho raha / Railway paise mang raha"
- Railway का free tier नहीं है → app बंद, data (SQLite ephemeral disk) खतरे में
- ✅ **FIXED (आज):** `START_LOCAL.bat` — laptop पर 5 मिनट में चलाएँ, data आपकी disk पर + auto-backup। पूरा research: `FREE_HOSTING_PLAN.md`

### Bonus bug मिला: Windows पर Admin login टूटा हुआ था
- `seed_default_admins()` में 🔐 emoji print Windows console पर crash करता था → CEO account कभी बनता ही नहीं था, super-admin का password console पर दिखता ही नहीं था → **"login hi nahi ho raha"** की एक बड़ी वजह
- ✅ **FIXED:** ASCII-safe prints + `admin_credentials.txt` file में credentials save

---

## 2. Lego Blocks — one by one plan

| Block | काम | Impact | Status |
|---|---|---|---|
| **B1** | Windows admin-seed crash fix + credentials file | Login काम करे | ✅ DONE |
| **B1** | Tracking link: auto-detect URL + patient message में link | Patient को waiting दिखे | ✅ DONE |
| **B1** | `START_LOCAL.bat` + `backup_now.py` + `BACKUP_DATA.bat` | App free चले, data safe | ✅ DONE |
| **B2** | Call/recall पर patient को WhatsApp (Cloud API auto-send या wa.me popup) | Patient को call पहुँचे | ✅ DONE 29-Aug |
| **B3** | Real department field + multi-department queue + **`_get_queue` UUID-crash & missing-`logger` FIX** + नए patient/call पर sound | TMT/ECG/Echo को patient दिखे | ✅ DONE 29-Aug |
| **B4** | Patient tracking page live polling (8s) + "आपका token बुलाया गया" banner + sound | Patient टोकन सुनकर आए | ✅ DONE 29-Aug |
| **B5** | **Clinic Live Board** (`/staff/live-board`): सब departments + waiting/called/ready एक screen पर, 10s auto-refresh + sound | पूरा clinic interconnected | ✅ DONE 29-Aug |
| **B6** | Doctor alerts: staff pages पर "नई रिपोर्ट तैयार" beep + OPD doctor portal पर "नया patient queue में" beep (20s poll) | Doctor का disruption खत्म | ✅ DONE 29-Aug |
| **B7** | `deploy_oracle.sh` + `CLOUD_DEPLOY_GUIDE.md`: Oracle/Google free VM, systemd, रोज़ 2× backup cron, Cloudflare Tunnel | 24/7 free hosting, data permanent | ✅ DONE 29-Aug (docs+script) |
| **B8** | WhatsApp Cloud API setup (Meta free tier) — direct auto-send, बिना popup | Messages automatic | ✅ DONE 29-Aug (guide + code-ready) |

**⚠️ आज का सबसे बड़ा fix (B3):** `_get_queue()` में phone-lookup string-UUID crash से **हमेशा fail हो रहा था**, और `staff_routes.py` में `logger` defined ही नहीं था (error handler भी crash) — मतलब **हर department page (TMT/ECG/Echo/Doctor/Reception) की queue खाली दिखती थी**। यही "receptionist add kare to TMT wale ko nahi milta" की असली जड़ थी। अब fix है और 3/3 tests से prove है।

**हर block के बाद मैं test चलाकर बताऊँगा कि क्या fix हुआ — आप एक-एक करके clinic में check करेंगे।**

---

## 3. आज शाम तक आपको बस यह करना है

1. `START_LOCAL.bat` double-click → server चलेगा, browser खुलेगा
2. Login करें: **Admin** (username/password `admin_credentials.txt` में — पहली बार चलाने पर बनती है), **Staff PINs** वही हैं (Reception 1234, Doctor 5678, Manager 9999, Admin 0000)
3. Clinic के दूसरे computers से `http://<laptop-IP>:8000` खोलें (IP START_LOCAL.bat में दिखता है)
4. Firewall popup → **Allow**
5. एक test patient register करें → देखें: WhatsApp में अब **live waiting link** आता है ✅
6. शाम को `BACKUP_DATA.bat` चलाएँ (या server बंद करने से पहले — auto-backup वैसे भी start पर होता है)
