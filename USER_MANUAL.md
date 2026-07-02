# 🏥 GIL CLINIC CardioQueue — User Manual & Operations Guide

Welcome to the **GIL CLINIC CardioQueue** patient flow management system! This system helps streamline patient registrations, coordinate queues across diagnostic departments (ECG, Echo, TMT, Holter, ABPM), and manage report generation and delivery.

---

## 🗄️ 1. Database & Coordination Modes

CardioQueue has **two database options** depending on how your clinic staff connects their mobile phones:

### Mode A: Local SQLite Mode (100% Free, Default)
- **What it does:** Saves all patient and test records locally in a file named `cardioqueue.db` on your clinic's main laptop. No online database setup is required.
- **How to coordinate staff on their mobiles:**
  1. Open a terminal on your clinic's laptop and start Streamlit (`python -m streamlit run app.py`).
  2. To let the receptionist, Bablu (technician), and the doctor access the app on their mobile phones using their SIM card internet data, install a free tunneling tool like **ngrok** or **localtunnel** on the laptop:
     ```bash
     # Install localtunnel globally via npm (if you have Node.js)
     npm install -g localtunnel
     lt --port 8501
     ```
  3. Localtunnel will generate a public URL (e.g., `https://gil-clinic.loca.lt`).
  4. Share this link with your staff. They can open it on their mobile phone browsers using cellular SIM data. Any change they make will automatically update the central `cardioqueue.db` on the clinic laptop!

### Mode B: Supabase Cloud Mode (Free Tier Online Database)
- **What it does:** Connects to a free online database on Supabase.
- **When to use:** If you prefer not to keep the clinic laptop running a tunneling tool, and want a database hosted in the cloud.
- **How to configure:**
  1. Go to [Supabase](https://supabase.com) and create a free project.
  2. Run the SQL schema in the SQL Editor from [supabase_schema.sql](file:///c:/Users/pc/Desktop/gurjas%20ai/GIL%20CLINIC/supabase_schema.sql).
  3. Copy your project URL and anon public key into your [.env](file:///c:/Users/pc/Desktop/gurjas%20ai/GIL%20CLINIC/.env) file.

---

## 💻 2. Local Environment Configuration

Open the [.env](file:///c:/Users/pc/Desktop/gurjas%20ai/GIL%20CLINIC/.env) file in a text editor to configure passwords and notification recipients:

```env
# 1. Staff Passwords (for logging in to their respective roles)
RECEPTION_PASS=recep123
ECG_PASS=ecg123
ECHO_PASS=echo123
TMT_PASS=tmt123
DOCTOR_PASS=doc123

# 2. Staff Phone Numbers (10-digit Indian numbers to receive WhatsApp alerts)
DOCTOR_MOBILE=9876543210
BABLU_MOBILE=9876543211
```

---

## 🚀 3. How to Run the App Locally

Ensure Python is installed, then run:

```bash
# Navigate to the project folder
cd "C:\Users\pc\Desktop\gurjas ai\GIL CLINIC"

# Install required packages
pip install -r requirements.txt

# Run the Streamlit application
python -m streamlit run app.py
```

The app will open at: **`http://localhost:8501`** (or `http://localhost:8502` if port 8501 is busy).

---

## 📋 4. Clinic Workflows & Staff Roles

### 1. Receptionist (OPD & Entry)
- **Register New Patient:** Enters patient details, mobile number, age, gender, and selects tests.
- **Prints Token:** Click **Print Token** to print the receipt.
- **Automatic WhatsApp Notification:** When saved, the system automatically runs a background task on the laptop to send a WhatsApp message to the patient (token details), the Doctor (new registration alert), and Bablu (diagnostics alert).

### 2. Technicians (Bablu - ECG / Echo / TMT)
- **Queue Management:** Bablu logs in on his mobile phone using his password (`ecg123`/`tmt123`).
- **Call Patient:** Bablu clicks **🔵 Call Patient**. The clinic laptop immediately sends a WhatsApp to the patient telling them to proceed to the room.
- **Complete Test:** Once done, Bablu clicks **✅ Complete**. The system notifies the patient via WhatsApp that their test is complete.

### 3. Doctor (Report Generation & Delivery)
- **Pending Reports:** Displays completed tests awaiting report approval.
- **Mark Report Ready:** Click **📋 Report Ready**. The system automatically updates the status and sends a WhatsApp to the patient to collect their report from the counter.
- **Mark Delivered:** Once handed over, click **📄 Delivered**.

---

## 📱 5. Free WhatsApp Web Automation Setup

To make the WhatsApp notifications work:
1. **Clinic Laptop Setup:** 
   - Keep a Chrome browser window open on the clinic laptop.
   - Go to [web.whatsapp.com](https://web.whatsapp.com) and log in using the clinic's dedicated Android phone (linked device QR code).
2. **Background Automation:**
   - The app has an asynchronous **background queue thread**.
   - When anyone performs an action (registers a patient, calls a patient, completes a test, or prepares a report) on their mobile phone, the Streamlit app on the clinic laptop puts the message in the queue.
   - The background thread sequentially opens a Chrome tab, types the message on WhatsApp Web, presses Enter, and closes the tab after sending.
   - This ensures that keyboard/mouse commands do not conflict and Streamlit never freezes or lags!

---

## 📱 6. Pure PWA + Google Sheets Shared Cloud Backend Setup (Mobile-first)

CardioQueue includes a mobile-optimized Pure PWA (Progressive Web App) that allows all clinic staff to sync their devices in real-time using a free Google Sheets cloud backend (no VPS or server setup cost!).

### Step 1: Google Sheet Banao (Create Google Sheet)
1. Open Chrome on your computer or mobile and go to: **https://sheets.new**
2. Name the sheet **"CardioQueue"** (at the top left). This sheet will act as your cloud database.

### Step 2: Apps Script code Lagao (Add Apps Script)
1. Inside the Google Sheet, go to **Extensions** -> **Apps Script** (or the ⋮ menu on mobile).
2. Delete any default code.
3. Open [Code.gs](file:///c:/Users/pc/Desktop/gurjas%20ai/GIL%20CLINIC/pwa/google-apps-script/Code.gs) in this project, copy all its contents, and paste it into the script editor.
4. Save the script (Ctrl+S / Save icon) and name it **"CardioQueue Backend"**.

### Step 3: Web App Deploy Karo (Deploy Web App)
1. Click the **Deploy** button -> **New Deployment**.
2. Select type: **Web App** (click the gear icon).
3. Set the following configurations:
   - **Execute as:** "Me (your-email@gmail.com)"
   - **Who has access:** **"Anyone"** (This is crucial for mobile sync).
4. Click **Deploy**, choose your Google account, and click **Allow** for permissions.
5. **Copy the Web App URL** displayed (e.g., `https://script.google.com/macros/s/abc123.../exec`).

### Step 4: Link URL in PWA (PWA Setup)
1. Open the PWA link on your mobile phone:  
   👉 **https://gurjeetsinghgill8-web.github.io/gil-clinic/pwa/index.html**
2. Login with any role (Reception, Doctor, etc.).
3. Click the **⚙️ Settings** icon in the bottom navigation.
4. Paste the copied Web App URL into the **Google Apps Script URL** field.
5. Click **Save URL** and click **Test Connection** (It should show "✅ Connected!").
6. *Repeat this on all staff phones. The URL is saved permanently on each phone, so you only need to enter it once!*

### Step 5: Start using (Real-time Sync)
- Now, when the receptionist registers a patient on their phone, the data is pushed to Google Sheets and instantly polled by the doctor's and technicians' phones (refreshes every 5 seconds).
- Patients can scan the QR code printed on their token to check their estimated waiting time and status live on their own phones!

