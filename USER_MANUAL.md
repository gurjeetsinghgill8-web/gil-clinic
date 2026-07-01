# 🏥 GIL CLINIC CardioQueue — User Manual & Operations Guide

Welcome to the **GIL CLINIC CardioQueue** patient flow management system! This system helps streamline patient registrations, coordinate queues across diagnostic departments (ECG, Echo, TMT, Holter, ABPM), and manage report generation and delivery.

---

## 🗄️ 1. Database Setup (Supabase)

CardioQueue uses **Supabase** as its real-time database. Follow these steps to provision it:

1. **Create a Supabase Account:** Go to [Supabase](https://supabase.com) and log in.
2. **Create a New Project:** 
   - Click **New Project** and select an organization.
   - Enter a name (e.g., `GIL CLINIC Queue`).
   - Create a strong database password (keep this safe).
   - Choose a region close to your clinic (e.g., *Asia Pacific (Mumbai)*).
3. **Create Tables & Policies:**
   - Go to the **SQL Editor** in the left sidebar of the Supabase dashboard.
   - Click **New query**.
   - Copy the entire contents of `supabase_schema.sql` and paste them into the SQL editor.
   - Click **Run** in the top right. This will create the `patients`, `tests`, and `messages` tables, index them for speed, and set up Row Level Security (RLS) policies.

---

## 💻 2. Local Environment Configuration

To run CardioQueue locally, you must configure the `.env` file in the root directory.

1. **Get API credentials from Supabase:**
   - Go to **Project Settings** (gear icon) → **API** in the Supabase dashboard.
   - Copy the **Project URL** and the **anon/public API key**.
2. **Update the `.env` file:**
   - Open `.env` in a text editor.
   - Replace the placeholder values with your actual URL and Anon key:
     ```env
     SUPABASE_URL=https://your-project-id.supabase.co
     SUPABASE_KEY=your-actual-anon-key-here
     ```
   - Customize the staff passwords if desired:
     - `RECEPTION_PASS=recep123`
     - `ECG_PASS=ecg123`
     - `ECHO_PASS=echo123`
     - `TMT_PASS=tmt123`
     - `DOCTOR_PASS=doc123`

---

## 🚀 3. How to Run the App Locally

Ensure you have Python installed, then execute the following commands in your terminal:

```bash
# Navigate to the project folder
cd "C:\Users\pc\Desktop\gurjas ai\GIL CLINIC"

# Install required packages
pip install -r requirements.txt

# Run the Streamlit application
python -m streamlit run app.py
```

The app will open automatically in your web browser at: **`http://localhost:8501`**

---

## 📋 4. Clinic Workflows & Staff Roles

The application divides workflows by role, selectable in the sidebar:

### 1. Receptionist (Password: `recep123`)
- **Register New Patient:** Enter the patient's name, mobile number, age, gender, and select the required tests. Click **Save**.
- **Print Token Slip:** After saving, a formatted token slip preview is generated. Click **Print Token** to send the slip directly to the clinic's receipt printer.
- **Track Registrations:** View a real-time list of all patients registered today at the bottom of the dashboard.

### 2. Technicians (Passwords: `ecg123`, `echo123`, `tmt123`)
- **Auto-Refresh Queue:** Technicians see a real-time list of patients waiting for their specific test. The page automatically refreshes every 5 seconds.
- **Call Patient:** When ready, click **🔵 Call Patient**. This sends a browser/sound notification and updates the status.
- **Start Test:** Once the patient enters the room, click **▶️ Start**.
- **Complete Test:** Once the test is finished, click **✅ Complete**. This removes the patient from the technician's queue and moves them to the Doctor's dashboard.

### 3. Doctor (Password: `doc123`)
- **Pending Reports:** Displays patients who have completed their tests and are waiting for their reports to be written/reviewed.
- **Mark Report Ready:** Click **📋 Report Ready** to indicate that the physical report has been signed and is waiting at the counter.
- **Mark Delivered:** Once the patient picks up the report, click **📄 Delivered** to close the file.

### 4. Patient Status Page (No Password Required)
- Patients can check their own live status by going to this page and typing in their **mobile number**.
- Displays the live progress of each registered test (Waiting 🟡, Called 🔵, In Progress 🟠, Completed ✅, Report Ready 📋).
- Shows an **Estimated Wait Time** based on their position in the queue.

---

## 📱 5. WhatsApp Integration (Phase 2)

To send automated text updates (token registration, room calls, and report collection warnings) directly to patients' phones:

1. **Install pywhatkit:**
   ```bash
   pip install pywhatkit pyautogui
   ```
2. **Dedicated Automation Device:** Set up a computer or VPS with WhatsApp Web logged in.
3. Keep a Chrome browser window open with WhatsApp Web connected. The app will automatically open tabs and send messages to patients.

---

## 🛠️ 6. Troubleshooting

- **"Awaiting data..." message on Home Page:** This means the application cannot connect to Supabase. Check your `.env` file URL and Anon key.
- **Streamlit command not found:** Ensure you run the app using `python -m streamlit run app.py` rather than just `streamlit run`.
- **Token numbers not resetting:** Make sure all database tables are created using the latest schema containing `registration_date` on the `patients` table.
