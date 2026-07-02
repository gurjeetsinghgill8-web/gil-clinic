# 🏥 CardioQueue — Google Sheets Backend Setup Guide

## Yeh guide mobile par bhi follow kar sakte hain (5 minute ka kaam hai)

---

## Step 1: Google Sheet Banao

1. **Apne mobile mein Chrome kholo**
2. Jaao: **https://sheets.new**
3. Aapka ek **nayi Google Sheet** khul jayegi
4. Is sheet ka naam upar likho: **"CardioQueue"**
5. Yeh sheet aapka **sara data store karegi** — Patients + Tests sab ismein save hoga

---

## Step 2: Apps Script Mein Code Paste Karo

1. **Sheet ke andar**, teen dots (⋮) ya **Extensions** menu mein jaao
2. **Apps Script** par click karo
3. Ek nayi tab khulegi — jo code hai use **delete** karo (Ctrl+A → Delete)
4. Ab **Code.gs** file ka content copy karo (jo maine diya hai)
5. Paste karo (Ctrl+V)
6. **Save** karo (Ctrl+S) — naam do **"CardioQueue Backend"**

---

## Step 3: Web App Deploy Karo

1. **Deploy** button par click karo → **New Deployment**
2. **Type**: "Web App" select karo
3. **Execute as**: "Me" (yahi rahne do)
4. **Who has access**: **"Anyone"** select karo (yeh IMPORTANT hai)
5. **Deploy** button par click karo
6. **"Allow"** permissions do (Google account select karo → Allow)
7. **COPY THE URL** jo dikhe — kuch aisa: `https://script.google.com/macros/s/abc123.../exec`

⚠️ **Yeh URL bahut important hai! Isse safe rakhna.**

---

## Step 4: PWA Mein URL Dalein

1. GitHub Pages par PWA kholo:  
   **https://gurjeetsinghgill8-web.github.io/gil-clinic/pwa/index.html**
2. **Reception** ya kisi bhi role se login karo
3. Bottom navigation mein **⚙️ Settings** button dikhega
4. Settings mein **Google Apps Script URL** field mein woh URL paste karo jo Step 3 mein copy kiya tha
5. **Save URL** button dabao
6. **"Test Connection"** button dabao — "✅ Connected!" aana chahiye

---

## Step 5: Registration Form Banao (APNA Google Sheet)

**Pehli baar jab koi patient register karega, toh Google Sheet apne aap Patients aur Tests columns bana legi.** Aapko kuch nahi karna.

Agar aap **pehle se** columns dekhna chahte hain, toh sheet mein yeh tabs ban jayenge:
- **Patients** tab — patient details (name, mobile, age, gender, etc.)
- **Tests** tab — test details (ECG, Echo, TMT, status, token, etc.)

---

## ⚠️ Important Baatein

### 📱 Har Phone Par Bas Ek Baar URL Dalna Hoga
- Reception ke mobile mein ek baar URL dal do
- Technician ke mobile mein bhi ek baar URL dal do
- Doctor ke mobile mein bhi ek baar URL dal do
- **Ek baar save karne ke baad, localStorage mein save ho jayega — baar baar nahi dalna padega**

### 🌐 Internet Jaroori Hai
- Ab data **Google Sheet (cloud)** mein save hoga
- Isliye **mobile data ya WiFi** chalna chahiye
- Agar kisi ke paas internet nahi hai, toh woh data nahi dekh payega
- **Chhota clinic hai toh mobile data sabke paas hota hai** — yehi solution hai

### 🔄 Auto-Sync
- Ab har 5 second mein data refresh hoga
- Reception ne patient register kiya → Technician ke phone par automatically dikhega
- Technician ne test complete kiya → Doctor ke phone par automatically dikhega
- **"Ek aadmi kuchh dale to dusre ko automatically mil jaaye"** — yeh ab possible hai!

### 🔒 Data Safety
- Aapka data **aapke Google account mein** safe hai
- Koi aur share kiye gaye sheet ko nahi dekh sakta
- **Shaam ko aap Google Sheet khol ke directly CSV export kar sakte hain** (File → Download → CSV)

### ❌ Problem: Agar Google Sheets kaam nahi kare
- Check karo ki **internet connected hai**
- Check karo ki **URL sahi hai** (Settings mein jaake)
- **Test Connection** button dabao
- Agar kaam nahi karta, toh dobara deploy karo (Step 3)

---

## Troubleshooting

### "Network Error" aata hai
➡️ Check karo ki **"Anyone"** access diya hai ya nahi
➡️ Dobara deploy karo

### Data nahi dikh raha
➡️ Settings mein **Test Connection** dabao
➡️ Agar fail ho, toh naya URL deploy karo

### Sabse easy tarika (agar koi issue ho):
1. Google Sheet kholo
2. Extensions → Apps Script
3. Deploy → Manage Deployments
4. **Delete** old deployment
5. Dobara **New Deployment** karo
6. Nayi URL copy karo
7. PWA Settings mein naya URL daalo

---

## Technical Details (Samajhne ke liye)

| Cheez | Kaam |
|-------|------|
| **Google Sheet** | Aapka database — saara data yahan store hota hai |
| **Google Apps Script** | Ek REST API jo Sheet ko read/write karta hai |
| **PWA (yeh app)** | Har 5 second mein API se data fetch karta hai |
| **Internet** | Mobile data ya WiFi — koi bhi chalega |

### Koi Server Nahi
- Koi VPS, koi cloud server, koi hosting nhi chahiye
- Sirf **Google account** chahiye (jo sabke paas hai)
- **100% Free**, ₹0 cost

---

## Setup Complete Hai?

✅ Google Sheet banayi?  
✅ Apps Script mein code paste kiya?  
✅ Web App deploy kiya?  
✅ PWA mein URL dala?  
✅ Test Connection successful?

**Ab aap multi-device clinic queue system ke liye ready hain!** 🎉

Har phone par PWA kholo → Settings mein URL daalo → sab ek saath kaam karega!
