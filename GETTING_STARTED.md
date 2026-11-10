# BloodBeacon — Getting Started

Welcome! You have just completed **Stage 1** of the BloodBeacon emergency blood-donor activation system. This guide will help you understand what's been built and how to move forward.

## 🎯 What Is BloodBeacon?

BloodBeacon is a college project that helps hospitals find eligible blood donors nearby when an emergency need arises. It:

1. **Finds eligible donors** based on NBTC medical rules (age, weight, hemoglobin, donation gaps)
2. **Predicts who will help** using AI trained on past donor responses
3. **Alerts donors** on WhatsApp in smart waves to maximize confirmations
4. **Confirms donors** and reveals their phone number only after they agree

## ✅ Stage 1 Status

**Stage 1 is complete!** You have:

- ✅ Flask web app (phone-first design, runs on `PORT=5001`)
- ✅ Supabase database schema (6 tables with proper indexes)
- ✅ Donor registration page
- ✅ Blood request submission page
- ✅ Request status tracking (pending_verification → active → fulfilled)
- ✅ Stage 1 match preview (exact blood group + city matching only)
- ✅ Staff dashboard (placeholder)
- ✅ 33 seed donors across all 8 blood groups
- ✅ 11 NBTC rules seeded
- ✅ 18 comprehensive tests (all passing)
- ✅ Git repository initialized

## 🚀 Quick Start

### 1. Run Tests (No Supabase Needed)

```bash
cd ~/Documents/Blood\ Beacon
source venv/bin/activate
pytest tests/test_stage1.py -v
```

**Expected result:** `18 passed in 0.06s` ✅

### 2. Start the App Locally

```bash
source venv/bin/activate
PORT=5001 python app.py
```

**Visit:** `http://localhost:5001`

### 3. Try It Out

1. **Home page:** See the three doors (Register, Request, Staff)
2. **Register as Donor:** Fill in your details → confirms registration
3. **Request Blood:** Submit a blood request → shows as "Pending Verification"
4. **View Match:** Click "View Details" on a request → shows exact-match donors
5. **Staff Dashboard:** See all requests with status badges

## 🗄️ Database Setup (Optional)

If you want to use a real Supabase database:

### Step 1: Create Supabase Account
- Go to [supabase.com](https://supabase.com)
- Create a free project

### Step 2: Get Your Credentials
- Go to **Settings → API** in your Supabase project
- Copy the **Project URL** (e.g., `https://xyz.supabase.co`)
- Copy the **Service Role Key** (labeled "secret")

### Step 3: Configure BloodBeacon
```bash
cd ~/Documents/Blood\ Beacon
cp .env.example .env
```

Edit `.env` with your credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here
```

### Step 4: Run Schema
- Go to your Supabase project → **SQL Editor**
- Copy the entire content of `schema.sql`
- Paste into the SQL editor and click **Run**

### Step 5: (Optional) Seed Data
```bash
source venv/bin/activate
python seed.py
```

This creates 33 test donors and 11 NBTC rules in your Supabase project.

## 📁 Project Structure

```
BloodBeacon/
├── app.py                    # Flask app (main entry point)
├── db.py                     # Database interface (all Supabase queries here)
├── seed.py                   # Seed script (creates test data)
├── schema.sql                # Database schema (copy-paste into Supabase)
├── requirements.txt          # Python dependencies
├── .env.example              # Template for your credentials
├── .gitignore                # Ignores .env and venv
├── README.md                 # Project overview
├── templates/                # HTML pages (Jinja2)
│   ├── home.html            # Home page
│   ├── register.html        # Donor registration
│   ├── request.html         # Blood request
│   ├── request_status.html  # Request status
│   ├── match_preview.html   # Stage 1 match preview
│   ├── staff_dashboard.html # Staff panel
│   ├── base.html            # Base template
│   ├── 404.html             # Error page
│   └── 500.html             # Error page
├── tests/                    # Test suite
│   ├── mock_db.py           # Mock database (for tests)
│   └── test_stage1.py       # 18 tests
└── venv/                     # Python virtual environment
```

## 🔑 Key Concepts

### Donor Registration
- Creates a donor record with: name, blood group, city, area, phone, gender, DOB, weight
- Phone is unique (can't register twice with same number)
- Status: always "active" when registered

### Blood Request
- Creates a request with: patient name, blood group, units, hospital, city, needed-by time
- Initial status: `pending_verification` (no alerts sent yet)
- Staff must verify before it becomes `active`
- Match preview only available after status changes to `active`

### Stage 1 Match Preview
- **Scope:** Exact blood group in the same city
- **Example:** B+ request in Tiruchirappalli shows only B+ donors in Tiruchirappalli
- **Not shown:** O+/O− (compatibility comes in Stage 2), deferred donors (eligibility comes in Stage 2)
- **Clearly labeled:** "Stage 1 Preview" with warning about missing features

### Database Module (db.py)
- **Single source of truth** for all database queries
- Reads credentials from `.env` (never hardcoded)
- Functions for every table: donors, requests, donations, rules, audit_log
- Tests use `mock_db.py` (in-memory) instead of real Supabase

## 📊 Seed Data

### Donors (33 total)
- **All 8 blood groups:** O+, O−, A+, A−, B+, B−, AB+, AB−
- **Two cities:** Tiruchirappalli (17) and Chennai (15)
- **Varied last-donation dates:** Some donors within 30 days, some 100+ days ago
- **All realistic:** Weight ≥45kg, age range 18–65, varied areas

### NBTC Rules (11)
- `age_min: 18` — Minimum age for donation
- `age_max: 65` — Maximum age for donation
- `weight_min_kg: 45` — Minimum weight
- `hemoglobin_min: 12.5` — Minimum hemoglobin level
- `donation_gap_men_days: 90` — Days between donations (men)
- `donation_gap_women_days: 120` — Days between donations (women)
- `tattoo_deferral_days: 365` — Deferral for tattoo/piercing
- Plus 4 TODO rules (pregnancy, major surgery, fever, antibiotics) — unverified, to be filled in

## 🧪 Testing

All tests pass without needing Supabase credentials. Tests include:

1. **Schema tests:** Verify all 6 tables exist with proper indexes
2. **Seed tests:** Verify blood groups, cities, and NBTC rules are seeded
3. **Registration tests:** Verify donor registration works
4. **Request tests:** Verify blood request submission works
5. **Match preview tests:** Verify exact-match filtering works correctly
6. **Navigation tests:** Verify all pages load

**Run tests:**
```bash
pytest tests/test_stage1.py -v
```

## 🔐 Security & Data Safety

✅ **Donor phone numbers are never exposed** on public pages
- Registration page: Only collects phone, doesn't show it back
- Match preview: Shows donor name/area/blood group, NOT phone
- Phone numbers only revealed after donor confirms (Stage 4)

✅ **All requests start as pending_verification**
- No alerts are sent until staff verifies
- Only verified requests show match previews

✅ **No secrets in code**
- Credentials read from `.env` (never committed)
- `.gitignore` prevents accidental commits

## 📝 Troubleshooting

### Q: Tests fail with module not found
**A:** Make sure you're using the venv:
```bash
source venv/bin/activate
pytest tests/test_stage1.py -v
```

### Q: App starts but says database not configured
**A:** This is fine for testing! To use Supabase:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Q: PORT 5001 is already in use
**A:** macOS reserves 5001 for AirPlay. Use a different port:
```bash
PORT=5002 python app.py
```

### Q: I want to reset the database
**A:** For local testing (no Supabase), tests automatically reset mock_db. For real Supabase:
- Go to Supabase SQL Editor
- Run: `TRUNCATE TABLE donors CASCADE; TRUNCATE TABLE requests CASCADE; ...`

## 🎯 What's Next: Stage 2

Stage 2 will add:

1. **Eligibility Engine**
   - Check donor age from DOB
   - Check weight ≥ 45 kg
   - Check last donation date (90 days for men, 120 for women)
   - Check deferrals (tattoo, surgery, fever, antibiotics, pregnancy)
   - Return: Eligible or Deferred Until [date] Because [reason]

2. **Compatibility Engine**
   - Blood-type compatibility matrix
   - Example: B+ request also shows O+, O− donors
   - Component-aware (whole blood vs platelets vs plasma)

3. **Updated Match Preview**
   - Show eligible status for each donor
   - Show compatible blood types (not just exact match)
   - Sort by eligibility

## 📚 Documentation

All documentation is in the repo:

- **README.md** — Project overview
- **BLOODBEACON_STATUS.md** — Build status tracker
- **STAGE1_HANDOFF.md** — Comprehensive handoff guide
- **STAGE1_SUMMARY.txt** — Quick summary
- **GETTING_STARTED.md** — This file
- **BloodBeacon-Context-For-Copilot.md** — Original requirements (in Downloads)

## 🤝 Questions?

Review these in order:
1. This file (GETTING_STARTED.md)
2. STAGE1_HANDOFF.md (comprehensive guide)
3. BLOODBEACON_STATUS.md (build status)
4. Code comments in app.py, db.py, and tests

## ✨ You're All Set!

Your BloodBeacon Stage 1 is complete and ready for development. To start building Stage 2:

1. Read the "What's Next" section above
2. Read Stage 2 requirements in BLOODBEACON_STATUS.md
3. Create a new branch for Stage 2 work
4. Update BLOODBEACON_STATUS.md as you progress

Happy coding! 🩸
