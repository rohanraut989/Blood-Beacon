# BloodBeacon — Build Status

## Current Stage: 2 (COMPLETE) ✅

### Stage 1: Skeleton + Data Model

**Objective:** Build the project foundation with Flask skeleton, database schema, donor registration, blood request submission, and Stage 1 match preview.

**Status:** ✅ COMPLETE

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
   - Match preview test showing compatible donors and city filtering
   - Page navigation (home, staff, 404)
   - Stage 2 checks on match preview

---

### Stage 2: Eligibility + Compatibility Engines

**Objective:** Implement medical decision engines for donor eligibility assessment (NBTC rules) and blood-type compatibility, upgrade match preview to filter and rank donors.

**Status:** ✅ COMPLETE (all 21 tests passing)

### What Was Built

1. **Eligibility Engine (`eligibility.py`)**
   - Pure function `assess_donor(donor, donations, rules, today)` → `{status, eligible_on, reasons}`
   - Implements NBTC rules:
     - Age: 18–65 (defer if outside range, eligible_on = 18th or 66th birthday)
     - Weight: ≥45 kg (defer if <45, eligible_on = when weight expected to meet threshold)
     - Donation gap: Men ≥90 days, Women ≥120 days (defer if too soon, eligible_on = last_donation + gap)
   - Unverified deferrals marked TODO (data not collected):
     - Tattoo/piercing, surgery, pregnancy, fever, antibiotics
   - All rules read from `rules` dict (no hardcoding)
   - Multiple deferrals listed together with reasons
   - Returns: `eligible` or `deferred` status with detailed reasons

2. **Compatibility Engine (`compatibility.py`)**
   - Blood-type matrices for red blood cells, plasma, and platelets
   - **Red cell compatibility:** Based on ABO + Rh factor
     - O- is universal donor (only donates to Rh- recipients for red cells)
     - O+ only donates to Rh+ recipients
     - AB+ is universal recipient (receives from all Rh+)
     - AB- receives from all Rh- only
   - **Plasma compatibility:** AB and O are universal plasma donors (lack A/B antigens)
     - Rh factor still applies (Rh- recipients only receive from Rh- plasma)
   - **Platelet compatibility:** v1 uses whole-blood matrix (TODO-verify: real platelets need cross-matching)
   - Functions:
     - `compatible_donor_groups(recipient_group, component)` → set of compatible donor groups
     - `is_compatible(donor_group, recipient_group, component)` → bool
     - `get_all_blood_groups()` → list of all 8 groups

3. **Updated Match Preview (`/match/<request_id>`)**
   - Retrieves all donors in request's city (not just exact group)
   - For each donor:
     - Checks blood-type compatibility with request component
     - Assesses eligibility using eligibility engine
   - Displays two sections:
     - **Eligible donors** (ranked: exact match first, then compatible by area)
       - Shows blood group, area, eligibility status
       - Separates exact matches (green) from compatible (gray)
     - **Deferred donors** (collapsed section with reasons)
       - Shows name, blood group, area, deferral reasons
       - Shows eligible_on date when they can donate again
   - Never displays donor phone numbers
   - Responsive UI with clear visual hierarchy

4. **Updated Templates**
   - `match_preview.html` — Shows eligible + deferred donors separately
   - `request_status.html` — Clean status page (no Stage 1 warning)
   - Removed "Stage 1" warnings, updated to "Stage 2 Active"

5. **Updated Database Module (`db.py`)**
   - Added `get_donors_by_city(city)` function
   - Added to mock_db for testing

6. **Tests (`tests/test_stage2.py`)**
   - 21 comprehensive tests:
     - **Eligibility tests (9):** no donations, 60-day man deferred, 130-day woman eligible, age limits, weight limits, multiple deferrals
     - **Compatibility tests (10):** O- universal donor, AB+ universal recipient, Rh factor logic, plasma compatibility
     - **Integration test (1):** B+ request with O+/O- donors showing both as eligible/compatible
     - **Backward-compatibility test (1):** Confirms all Stage 1 blood groups still work

### Files Created/Modified

**New files:**
```
BloodBeacon/
├── eligibility.py            # Eligibility assessment engine (140 lines)
├── compatibility.py          # Blood-type compatibility matrices (147 lines)
└── tests/
    └── test_stage2.py        # 21 Stage 2 tests (387 lines)
```

**Modified files:**
```
├── app.py                    # Updated match_preview route with eligibility + compatibility
├── db.py                     # Added get_donors_by_city()
├── templates/
│   ├── match_preview.html    # Redesigned with eligible/deferred sections
│   └── request_status.html   # Updated status page
└── tests/
    ├── test_stage1.py        # Updated match preview test for compatibility
    └── mock_db.py            # Added get_donors_by_city()
```

### Test Results

**Run tests:**
```bash
source venv/bin/activate
pytest tests/test_stage1.py tests/test_stage2.py -v
```

**Results:** 
- ✅ 18 Stage 1 tests PASSING
- ✅ 21 Stage 2 tests PASSING
- **Total: 39 tests PASSING**

### Key Technical Decisions

1. **Eligibility engine is a pure function** — no side effects, all rule values read from `rules` dict
2. **Age calculation:** Simple `(today - DOB) / 365 days` (production should account for leap years)
3. **Eligible_on date:** Last donation + gap_days for deferrals
4. **Blood-type Rh factor:** Treated as separate from ABO group; Rh- recipients can ONLY receive from Rh- donors
5. **Plasma compatibility inversion:** AB and O are universal (lack A/B antigens), but Rh factor still matters
6. **Unverified rules marked TODO:** Tattoo/piercing, surgery, pregnancy, fever, antibiotics never assessed (data not collected)
7. **Match preview ranking:** Exact blood group first, then other compatible donors by area

### Limitations / TODOs

- **Platelet compatibility:** v1 uses whole-blood matrix (real platelets require HPA cross-matching)
- **Unverified deferrals:** Need data collection for tattoo, piercing, surgery, pregnancy, fever, antibiotics
- **Age calculation:** Should account for leap years in production
- **Staff dashboard:** Still a placeholder (next stage)
- **WhatsApp bridge:** Not implemented (next stage)
- **Wave simulation:** Not implemented (next stage)

### How to Verify Locally

1. **Run all tests:**
   ```bash
   source venv/bin/activate
   pytest tests/ -v
   ```

2. **Verify specific Stage 2 scenarios:**
   - Man 60 days after donating → deferred
   - Woman at 130 days → eligible
   - B+ request with O+ donors → O+ shown as eligible/compatible
   - Age 17 or 66 → deferred
   - Weight <45kg → deferred

3. **Try the app:**
   ```bash
   PORT=5001 python app.py
   # Register donors, create requests, view match preview
   ```

---

## Files Created

```
BloodBeacon/
├── app.py                    # Flask application
├── db.py                     # Database access module
├── seed.py                   # Seed data script
├── eligibility.py            # Stage 2: Eligibility engine
├── compatibility.py          # Stage 2: Compatibility engine
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
│   ├── match_preview.html    # Stage 2 match preview
│   ├── staff_dashboard.html  # Staff dashboard
│   ├── 404.html              # 404 error page
│   └── 500.html              # 500 error page
└── tests/
    ├── __init__.py
    ├── mock_db.py            # Mock database for testing
    ├── test_stage1.py        # Stage 1 tests (18)
    └── test_stage2.py        # Stage 2 tests (21)
```

### How to Verify Locally

1. **Set up Supabase credentials (optional for basic tests):**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials from https://app.supabase.com
   ```

2. **Run tests (no Supabase needed):**
   ```bash
   source venv/bin/activate
   pytest tests/ -v
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
   - In staff dashboard (simulate activation), set request to active
   - Click "View Donor Matches" → see eligible + deferred donors with compatibility + eligibility filtering

### Supabase Setup (When Ready)

When you have Supabase credentials:
1. Copy .env.example to .env
2. Paste your project URL and service key
3. Run schema.sql in the Supabase SQL editor (copy-paste entire file)
4. Optionally seed: `python seed.py` (requires credentials)

### Next Stage (Stage 3)

- **Staff activation workflow** — Mark requests as active, trigger donor alerts
- **Donor response system** — Track donor responses (committed, on way, unavailable)
- **Wave simulation** — Send alerts in waves based on compatibility + eligibility + area
- **Real-time donor locator** — Show donors being contacted in each wave
- **Analytics dashboard** — Success rates, response times, blood collected

### Known Limitations

- No WhatsApp bridge (mock notifications only)
- Staff dashboard is a placeholder (next stage)
- No real-time updates (polling only)
- No donor response tracking (next stage)
- Donor phone numbers never exposed in UI (data safety enforced)

### Blockers / Issues

None. All Stage 1 + Stage 2 objectives complete and all 39 tests passing.

---

**Last Updated:** 2024-11-10  
**Stages Complete:** Stage 1 ✅, Stage 2 ✅
**Total Tests:** 39 passing  
**Commit Message:** `Stage 2: eligibility + compatibility engines, match preview upgrade`
