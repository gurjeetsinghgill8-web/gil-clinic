# 🚀 CardioQueue — Deployment Guide

## 📋 Prerequisites

1. **Supabase Account** (free): https://supabase.com
2. **Streamlit Cloud Account** (free): https://streamlit.io/cloud
3. **GitHub Account** (free): https://github.com

---

## 🗄️ Step 1: Set Up Supabase Database

1. Go to [supabase.com](https://supabase.com) → **Create a new project**
2. Choose a name (e.g., `cardioqueue`) and a strong database password
3. Wait for the database to provision (~2 minutes)
4. Go to **SQL Editor** in the left sidebar
5. Copy the entire contents of `supabase_schema.sql` and paste it
6. Click **Run** — all tables will be created

### Get Your API Keys

1. Go to **Project Settings** → **API**
2. Copy the **Project URL** and **anon/public key**
3. These go into your `.env` file

---

## 💻 Step 2: Configure Environment

Edit `.env` in the project root:

```env
# Supabase — replace with your actual credentials
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key-here

# Staff Passwords (change these!)
RECEPTION_PASS=recep123
ECG_PASS=ecg123
ECHO_PASS=echo123
TMT_PASS=tmt123
DOCTOR_PASS=doc123

# Hospital Info
APP_NAME=CardioQueue
HOSPITAL_NAME=GIL CLINIC

# Average test durations (minutes)
AVG_ECG_TIME=10
AVG_ECHO_TIME=20
AVG_TMT_TIME=30
AVG_HOLTER_TIME=15
AVG_ABPM_TIME=15
```

> ⚠️ **Never commit `.env` to GitHub!** It's already in `.gitignore`.

---

## 🧪 Step 3: Test Locally

```bash
cd "C:\Users\pc\Desktop\gurjas ai\GIL CLINIC"

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

### Test the Workflow:

1. **Login as Reception** → password: `recep123`
2. Register a test patient (Name, Mobile, Age, Gender, Tests)
3. **Login as ECG/Echo/TMT** → password: `ecg123`/`echo123`/`tmt123`
4. See the patient in waiting list → Click **Call Patient**
5. Click **Start** → Click **Complete**
6. **Login as Doctor** → password: `doc123`
7. See completed test → Click **Report Ready**
8. Click **Delivered**
9. **Patient Status** page — enter mobile number → see live status

---

## ☁️ Step 4: Deploy to Streamlit Cloud

### Option A: Deploy from GitHub (Recommended)

1. Create a **new GitHub repository**
2. Push this project to GitHub:

```bash
cd "C:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
git init
git add .
git commit -m "Initial commit — CardioQueue v1.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/cardioqueue.git
git push -u origin main
```

3. Go to [share.streamlit.io](https://share.streamlit.io)
4. Click **Deploy an app**
5. Authorize GitHub, select the `cardioqueue` repo
6. Set:
   - **Branch:** `main`
   - **Main file:** `app.py`
7. Click **Advanced settings** → **Secrets**
8. Add all your `.env` variables one by one (or use the **Upload .env** option)
9. Click **Deploy**

### Option B: Direct Deploy (Alternative)

If you prefer not to use GitHub:

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **Deploy an app** → **Paste GitHub URL**
3. Or use the Streamlit CLI:
   ```bash
   streamlit deploy
   ```

---

## 📱 Step 5: Sharing with Staff

Once deployed, your app will have a URL like:
```
https://YOUR_USERNAME-cardioqueue-app-XXXXXX.streamlit.app
```

Share this URL with:
- **Reception staff** — use the Reception page
- **Technicians** — use ECG/Echo/TMT pages
- **Doctor** — use Doctor page
- **Patients** — use Patient Status page (no login needed)

> 💡 **Tip:** Create a QR code of the patient status page URL and put it at the reception counter so patients can check their status on their own phone.

---

## 🔔 Phase 2: WhatsApp Setup

When ready for WhatsApp notifications:

1. Install additional dependencies:
   ```bash
   pip install pywhatkit pyautogui
   ```

2. Set up a dedicated Android phone:
   - Install WhatsApp Business
   - Keep WhatsApp Web connected 24/7
   - Keep Chrome browser open

3. The WhatsApp automation in `utils/whatsapp.py` will auto-detect when pywhatkit is installed and start sending messages.

---

## 📊 Monitoring

- **Supabase Dashboard** — View all tables, run queries, see real-time data
- **Streamlit Cloud Dashboard** — View app logs, restart, manage secrets

---

## 🔄 Updating

1. Make changes locally
2. Push to GitHub:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```
3. Streamlit Cloud auto-deploys from the `main` branch

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `Supabase not connected` | Check `.env` values, ensure Supabase project is running |
| `Module not found` | Run `pip install -r requirements.txt` |
| `Login fails` | Check password in `.env` matches what you typed |
| `Blank page` | Check Streamlit Cloud logs in the dashboard |
| `Token not assigned` | Ensure `tests` table has proper auto-increment setup |
| `Slow page load` | Reduce auto-refresh interval (default is 5s) |

---

## 📞 Support

For issues or feature requests, contact the development team.
