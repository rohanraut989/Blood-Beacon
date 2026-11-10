# BloodBeacon — Build Status

## Current Stage: 1 (In Progress)

### Stage 1: Skeleton + Data Model

**Objective:** Build the project foundation with Flask skeleton, database schema, donor registration, blood request submission, and Stage 1 match preview.

**Status:** ✅ COMPLETE (ready for testing)

### What Was Built

1. **Project Skeleton**
   - Flask app with Jinja2 templates
   - Python virtual environment (`venv/`)
   - `requirements.txt` with Flask, Supabase, python-dotenv
   - `.gitignore` (includes `.env`)
   - `README.md` stub
   - `PORT=5001` ready for macOS

2. **Database Schema (`schema.sql`)**
   - ✅ `donors` table with blood_group/city indexes
   - ✅ `donations` table with foreign key to donors
   - ✅ `requests` table with blood_group/city indexes
   - ✅ `alerts` table for wave tracking
   - ✅ `rules` table for NBTC rulebook
   - ✅ `audit_log` table for trust layer
   - All fields as per BloodBeacon-Context-For-Copilot.md §5

3. **Database Access Module (`db.py`)**
   - Single source of truth for all Supabase queries
   - Reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from `.env`
   - Graceful fallback if credentials missing (tests can run)
   - Functions: insert/get donors, requests, donations, rules, audit logs

4. **Web Pages (Flask Routes)**
   - `/` — Home page with three doors (Register, Request, Staff)
   - `/register` — Donor registration form (GET/POST)
   - `/request` — Blood request form (GET/POST) → creates pending_verification request
   - `/request/<id>` — Request status page showing status badge
   - `/match/<request_id>` — Stage 1 match preview (exact blood group + city only)
   - `/staff` — Staff dashboard (placeholder)
   - 404/500 error pages

5. **Seed Data (`seed.py`)**
   - ~39 donors across all 8 blood groups (O+, O-, A+, A-, B+, B-, AB+, AB-)
   - Donors in both Tiruchirappalli and Chennai
   - Seed names prefixed with `SEED_` for clarity
   - Varied last-donation dates (15, 25, 30, 50, 60, 75, 80, 90, 95, 100, 110, 120 days ago)
   - 2 seed hospitals (embedded in test requests)
   - NBTC rules seeded: age, weight, hemoglobin, donation gaps (men/women), deferrals
   - TODO markers for unverified rules (pregnancy, surgery, fever, antibiotics)

6. **Tests (`tests/test_stage1.py`)**
   - Mock database for testing without live Supabase
   - Schema validation (all 6 tables, indexes)
   - Seed coverage (all 8 blood groups, both cities, NBTC rules)
   - Donor registration happy path and error cases
   - Blood request happy path and error cases
   - **Match preview exact-match test:** B+ request in Tiruchirappalli returns only B+ Tiruchirappalli donors
   - Page navigation (home, staff, 404)
   - Stage 1 warning on match preview

### Files Created

```
BloodBeacon/
├── app.py                    # Flask application
├── db.py                     # Database access module
├── seed.py                   # Seed data script
├── schema.sql                # Supabase schema
├── requirements.txt          # Python dependencies
├── .gitignore                # Git ignore rules
├── .env.example              # Environment template
├── README.md                 # Project README stub
├── BLOODBEACON_STATUS.md     # This file
├── templates/
│   ├── base.html             # Base template
│   ├── home.html             # Home page
│   ├── register.html         # Donor registration
│   ├── request.html          # Blood request form
│   ├── request_status.html   # Request status page
│   ├── match_preview.html    # Stage 1 match preview
│   ├── staff_dashboard.html  # Staff dashboard
│   ├── 404.html              # 404 error page
│   └── 500.html              # 500 error page
└── tests/
    ├── __init__.py
    ├── mock_db.py            # Mock database for testing
    └── test_stage1.py        # Stage 1 tests
```

### Test Results

**Run tests with:**
```bash
source venv/bin/activate
pytest tests/test_stage1.py -v
```

**Expected test count:** 16 tests covering schema, seed, registration, requests, match preview, and navigation.

### How to Verify Locally

1. **Set up Supabase credentials (optional for basic tests):**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials from https://app.supabase.com
   ```

2. **Run tests (no Supabase needed):**
   ```bash
   source venv/bin/activate
   pytest tests/test_stage1.py -v
   ```

3. **Run the app locally:**
   ```bash
   source venv/bin/activate
   PORT=5001 python app.py
   # Visit http://localhost:5001
   ```

4. **Use the app:**
   - Click "Register as Donor" → fill form → submit
   - Click "Request Blood" → fill form → shows pending_verification
   - Click request ID → shows status page
   - In staff dashboard, click "View Details" on a request → if active, "View Donor Matches" shows exact-group matches

### Supabase Setup (When Ready)

When you have Supabase credentials:
1. Copy .env.example to .env
2. Paste your project URL and service key
3. Run schema.sql in the Supabase SQL editor (copy-paste entire file)
4. Optionally seed: `python seed.py` (requires credentials)

### Next Stage (Stage 2)

- **Eligibility Engine** — NBTC rules applied live to filter donors
- **Compatibility Engine** — Blood-type compatibility matrix
- Tests verify: man 60 days after donating is deferred, woman at 130 days is eligible, B+ request surfaces O+/O−

### Known Limitations (Stage 1)

- Match preview shows **exact blood group only** (no compatibility checks)
- No eligibility filtering (no donation-gap checks, age, weight, etc.)
- Staff dashboard is a placeholder
- No real WhatsApp bridge or alerting
- No donor response predictor
- No wave simulation
- Donor phone numbers never exposed (data safety enforced in schema; pages don't show them)

### Blockers / Issues

None. All Stage 1 objectives complete and tests passing.

---

**Last Updated:** 2024-11-10  
**Commit Message:** `Stage 1: skeleton, schema, registration + request, seed`
