# BloodBeacon — Build Status

## Current Stage: 6.1.1 (COMPLETE) ✅

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
   - **Plasma compatibility (Stage 2.1 CORRECTION):** Based on donor plasma ANTIBODIES, NOT ABO blood type
     - AB plasma: no A/B antibodies → can go to ALL recipients (Rh-agnostic)
     - A plasma: has B antibodies → can go to A and O recipients ONLY (Rh-agnostic)
     - B plasma: has A antibodies → can go to B and O recipients ONLY (Rh-agnostic)
     - O plasma: has A/B antibodies → can go to O recipients ONLY (Rh-agnostic)
     - **Rh factor does NOT matter for plasma** (corrected from initial Stage 2 implementation)
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

6. **Eligibility Enhancement (Stage 2.1)**
   - Fixed `eligible_on` hygiene:
     - Time-based deferrals (age < 18, donation gap): `eligible_on` = specific date
     - Permanent conditions (weight < 45kg, age > 65): `eligible_on` = None
   - Added tests for eligible_on correctness

7. **Tests (`tests/test_stage2.py`)**
   - 27 comprehensive tests (expanded in Stage 2.1):
     - **Eligibility tests (12):** no donations, 60-day man deferred, 130-day woman eligible, age limits, weight limits, multiple deferrals, eligible_on hygiene
     - **Compatibility tests (13):** O- universal donor, AB+ universal recipient, Rh factor logic, plasma compatibility (corrected), full RBC table verification
     - **Integration test (1):** B+ request with O+/O- donors showing both as eligible/compatible
     - **Backward-compatibility test (1):** Confirms all Stage 1 blood groups still work

### Files Created/Modified

**New files:**
```
BloodBeacon/
├── eligibility.py            # Eligibility assessment engine (130+ lines)
├── compatibility.py          # Blood-type compatibility matrices (corrected plasma)
└── tests/
    └── test_stage2.py        # 27 Stage 2 tests (expanded in Stage 2.1)
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

### Test Results (Stage 2.1)

**Run tests:**
```bash
source venv/bin/activate
pytest tests/ -v
```

**Results:** 
- ✅ 18 Stage 1 tests PASSING
- ✅ 27 Stage 2 tests PASSING (expanded with corrections)
- **Total: 45 tests PASSING**

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

---

### Stage 2.1: Medical Matrix Corrections + Hygiene

**Objective:** Verify and correct blood-type compatibility matrices, fix eligible_on hygiene, add comprehensive tests.

**Status:** ✅ COMPLETE (45 tests passing, all corrections verified)

**Corrections Made:**

1. **Red-Cell Matrix Verification**
   - ✅ Full 8×8 matrix verified against canonical transfusion chart
   - ✅ Added `test_red_cell_compatibility_full_table()` with source citation
   - All 8 blood groups correct (O-, O+, A-, A+, B-, B+, AB-, AB+)

2. **Plasma Matrix Correction**
   - ✗ Initial Stage 2 plasma logic was WRONG (used Rh factor; treated O as universal)
   - ✅ **CORRECTED to:** Based on donor plasma ANTIBODIES, not ABO blood type
   - ✅ **Rh factor does NOT matter for plasma** (critical correction)
   - AB plasma → all recipients (universal, Rh-agnostic)
   - A plasma → A and O recipients ONLY (Rh-agnostic)
   - B plasma → B and O recipients ONLY (Rh-agnostic)
   - O plasma → O recipients ONLY (Rh-agnostic)
   - Edge case verified: "AB- plasma can go to O+" ✓, "O plasma cannot go to A" ✓

3. **Eligible_On Hygiene**
   - ✓ Time-based deferrals: eligible_on = specific date (18th birthday, donation gap date)
   - ✓ Permanent conditions: eligible_on = None (weight, age > 65)
   - ✓ Added tests verifying both cases

4. **Platelet Compatibility**
   - ✓ Unchanged: v1 uses whole-blood matrix with TODO-verify marker

**Test Expansion:**
- Stage 2: 21 tests → Stage 2.1: 27 tests
- Added: `test_eligible_on_is_date_for_time_based_deferrals`
- Added: `test_eligible_on_is_none_for_weight_deferral`
- Added: `test_eligible_on_is_none_for_over_65_deferral`
- Added: `test_red_cell_compatibility_full_table`
- Updated: `test_AB_positive_plasma_compatibility` (now Rh-agnostic)
- Added: `test_O_plasma_not_universal`
- Added: `test_A_plasma_compatibility`
- Added: `test_B_plasma_compatibility`

**All Previous Tests Passing:**
- Stage 1 tests: 18/18 passing ✓
- Stage 2 tests: 27/27 passing ✓
- **Total: 45/45 passing** ✓

---

### Stage 3: Donor Response Predictor (AI)

**Objective:** Build a scikit-learn model to predict donor show-up probability based on synthetic history, rank eligible donors by predicted show-up, and integrate into match preview.

**Status:** ✅ COMPLETE (56 tests passing; 11 Stage 3 tests + 45 Stage 1+2 backward compatible)

**What Was Built:**

1. **Training Data Generator (`make_training_data.py`)**
   - ✅ Generates `data/training_outcomes.csv` with 600 rows (deterministic, fixed seed)
   - ✅ Features: days_since_last_donation, total_donations, alerts_last_30d, past_response_rate, past_showup_rate, same_area, hour_of_day
   - ✅ Label: showed_up (0/1) generated from documented SYNTHETIC RULE
   - ✅ SYNTHETIC RULE documented in code: base 50%, +20% response/showup, +10% same_area, -3% per alert (fatigue), -10% if <5 days since donation, -5% if inconvenient hours, ±10% noise
   - ✅ Both labels (0 and 1) present in CSV

2. **Predictor Module (`predictor.py`)**
   - ✅ `train_model()`: trains LogisticRegression on synthetic CSV with StandardScaler, saves to `models/predictor.joblib`
   - ✅ Model accuracy: **70.0%** (beats baseline 69.2%)
   - ✅ `score_donor(features)` → returns probability in [0, 1]
   - ✅ `rank_donors(request, eligible_donors, donations_by_donor, alerts_by_donor, today)` → list of (donor, score, reason)
   - ✅ Reasons: "replies often", "shows up reliably", "same area", "well rested", "alerted often recently", "too soon after donation", "outside convenient hours", "neutral history"
   - ✅ New donors (no history) get neutral rates (0.5), never zeros

3. **Match Preview Integration**
   - ✅ Eligible donors now ranked by predicted show-up probability (best first)
   - ✅ Each row shows: name, area, blood group, ELIGIBLE status, **percentage (0-100%)**, and reason
   - ✅ Exact-match blood group visually marked
   - ✅ Honest disclaimer on page: "Ranking by predicted show-up probability — model trained on synthetic history in this version."
   - ✅ Deferred section unchanged

4. **Database Support**
   - ✅ Added `db.get_alerts_for_donor()` for future Stage 4+ (returns [] for now)
   - ✅ Mock DB supports alerts stub

5. **Tests**
   - ✅ Test CSV generates deterministically (same seed → same hash)
   - ✅ Test CSV has 600 rows with both labels
   - ✅ Test model trains and saves successfully
   - ✅ Test accuracy in [0, 1] and beats baseline
   - ✅ Test score_donor returns [0, 1] probability
   - ✅ Test new donor gets reasonable score (>0.3), not minimum
   - ✅ Test ranking fixture: Donor A (same area, high rates, no alerts, well-rested) beats Donor B (different area, low rates, 6 alerts, recent donation)
   - ✅ Test ranking returns donor, score, and reason

**Accuracy Report:**
- Held-out accuracy: **70.0%** (tested on 20% held-out set)
- Baseline accuracy: **69.2%** (majority class)
- **Model beats baseline: ✓**

**All Tests Passing:**
- Stage 1 tests: 18/18 passing ✓
- Stage 2 tests: 27/27 passing ✓
- Stage 3 tests: 11/11 passing ✓
- **Total: 56/56 passing** ✓

**Important Notes:**
- Model is trained on **SYNTHETIC data only** (no real alert outcomes yet)
- Accuracy is advisory; the model will retrain on real data in Stage 4+
- The synthetic rule is honest and documented; never presented as real to users
- UI explicitly warns users about synthetic training data

---

### Next Stage (Stage 4)

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

None. All Stage 1 + Stage 2 + Stage 2.1 + Stage 3 objectives complete and all 56 tests passing.

---

## Stage 4: Wave Alerting + Simulator

**Objective:** Implement wave-based donor alerting, seeded reply simulation, and simulator controls for testing fulfillment, privacy, and mark-donated flows.

**Status:** ✅ COMPLETE

### What Was Built

1. **Pure Wave Planner (`alerting.py`)**
   - `plan_waves(ranked_eligible, request, alerts_by_donor, now)` — Divides eligible donors into:
     - Wave 1 ≤ 10 donors (priority matches + high predicted responders)
     - Wave 2 ≤ 20 donors (queued if Wave 1 insufficient)
   - Anti-spam: Donors with 4+ alerts in last 30 days skipped (marked with "monthly cap" reason)
   - Quiet hours check (21:00-08:00): Recorded as policy note, does not block simulator alerts

2. **Deterministic Reply Simulator (`alerting.py`)**
   - `determine_reply(donor, score, seeded_rng)` → "confirmed" | "declined" | "no_reply"
   - Uses per-request seeded RNG (seed = request_id) for reproducible testing
   - High score (>0.7) → 70% confirm, 20% decline, 10% no_reply
   - Medium score (0.3-0.7) → 30% confirm, 40% decline, 30% no_reply
   - Low score (<0.3) → 5% confirm, 70% decline, 25% no_reply

3. **Activation Flow**
   - `/request/<id>/activate` (POST) — Staff endpoint to activate pending_verification request
   - On activate:
     - Get eligible donors (compatibility + eligibility filter)
     - Rank via Stage 3 predictor
     - Call plan_waves() to assign donors to Wave 1/2
     - Write Wave 1 alerts to DB (channel="simulator")
     - Change request status to "active"
     - Log to audit_log

4. **Simulator Advance Logic**
   - `/request/<id>/advance` (POST) — Staff button to advance the simulation
   - On advance:
     - Fetch Wave 1 alerts, simulate replies (seeded RNG per request)
     - Update alert.reply for each
     - Count confirmed donors
     - If confirmed ≥ units_needed: Mark request as "fulfilled", log
     - Else: Plan fresh wave (reuse eligible), fire Wave 2 (channel="simulator"), log
   - Ensures reproducible testing: same request_id always produces same reply sequence

5. **Privacy Enforcement**
   - Donor phone numbers ONLY visible in staff view if alert.reply == "confirmed"
   - Unconfirmed/declined donors' contact info never shown (prevents accidental staff leaks)
   - Tests verify this constraint in template rendering

6. **Mark Donated Flow**
   - `/request/<id>/donor/<donor_id>/mark-donated` (POST) — Staff button
   - On mark-donated:
     - Verify alert.reply == "confirmed"
     - Write donations row (request_id linked, source="simulator")
     - Update alert.showed_up = true
     - Log to audit_log
   - Donors immediately re-assess eligibility (become deferred if needed)

7. **Integration with App**
   - Updated `/request/<id>` to show alerts and staff controls
   - Added imports: `alerting`, `random`, `date`
   - Request status page shows:
     - Wave 1/Wave 2 donor lists (names, blood group, predicted score, reason)
     - Activate button (visible if pending_verification, staff=1)
     - Advance button (visible if active, staff=1)
     - Mark donated button per confirmed donor

### Test Coverage

**17 new tests in `test_stage4.py`:**
- `TestAlertingPlanner` (6 tests): Wave sizes, anti-spam, quiet hours, input validation
- `TestReplySimulation` (2 tests): Score-based reply distributions
- `TestActivationFlow` (2 tests): Activation writes Wave 1, changes status
- `TestFulfillment` (2 tests): Enough confirmations → fulfilled; shortfall → Wave 2
- `TestPrivacy` (2 tests): Phone visibility rule (confirmed only)
- `TestMarkDonated` (3 tests): Donations row write, showed_up flag, deferred re-assessment

**Backward Compatibility:**
- All 56 previous tests (Stage 1-3) still passing
- **Total: 73 tests passing**
- No changes to eligibility/compatibility logic (Stages 1-2 remain intact)
- Predictor interface unchanged (Stage 3 rank_donors still used)

### Key Files Modified

| File | Changes |
|------|---------|
| `app.py` | Added alerting import; 3 new routes (activate, advance, mark-donated) |
| `alerting.py` | NEW: plan_waves(), determine_reply() |
| `tests/test_stage4.py` | NEW: 17 comprehensive tests |
| `BLOODBEACON_STATUS.md` | Added Stage 4 section |

### Technical Decisions

1. **Seeded RNG per request:** `random.Random(request_id)` ensures deterministic replies for the same request across multiple advance calls. Simplifies testing; real deployments can seed by (request_id, timestamp) for variation.

2. **Quiet hours record but don't block:** Policy note aids auditing; simulator doesn't respect them (would confuse testing). Real SMS/WhatsApp integration (Stage 6) will honor them.

3. **Donations row links to request:** `donations.request_id` enables audit trail and per-request fulfillment tracking.

4. **No stored scores in alerts:** Predicted probability is computed fresh per ranking. If needed for later audit, could add `predicted_score` column to alerts table.

### Assumptions & Future Enhancements

- Single request in simulator at a time (UI doesn't prevent multiple active; tests assume one)
- Wave 2 auto-fires on advance if shortfall (no user pause option yet)
- Quiet hours affect audit/reporting but not simulator logic (Stage 6 will enforce)
- Donor unavailability/decline reasons not stored beyond reply enum

---

**Last Updated:** 2024-11-10  
**Stages Complete:** Stage 1 ✅, Stage 2 ✅, Stage 2.1 (Corrections) ✅, Stage 3 (Predictor) ✅, Stage 4 (Alerting) ✅
**Total Tests:** 73 passing (18 Stage 1 + 27 Stage 2 + 11 Stage 3 + 17 Stage 4)
**Commits:**
  - Stage 2: `eligibility + compatibility engines, match preview upgrade`
  - Stage 2.1: `plasma matrix correction + RBC table test`
  - Stage 3: `donor response predictor`
  - Stage 4: `wave alerting + simulator` (coming)

## Stage 5: Staff Dashboard + Experiment Mode

**Objective:** Implement staff verification workflow, request dashboard with status grouping, donor directory with eligibility badges, and experiment mode to compare alerting strategies on synthetic donors.

**Status:** ✅ COMPLETE

### What Was Built

1. **Verification Workflow** (`app.py` + `db.py`)
   - `/request/<id>/verify` (POST) — Staff marks request as verified (sets `verified_by`, status="verified")
   - `/request/<id>/reject` (POST) — Staff rejects with reason (status="rejected", audit log entry)
   - Activation now requires verified status; unverified returns 409 Conflict
   - All POST endpoints check `?staff=1` flag for security (returns 403 without it)

2. **Staff Dashboard** (`/staff` GET)
   - Request queue grouped by status: pending_verification, verified, active, fulfilled, rejected
   - Request detail shows waves sent, per-donor reply states, confirmed donors with phone numbers
   - Mark donated button for confirmed donors (writes donation, updates eligibility)
   - Close request functionality

3. **Donor Directory** (`/staff/donors` GET)
   - All donors with live Stage 2 eligibility badges (Eligible / Deferred until <date> — <reason>)
   - Filter by blood group and city
   - Phone numbers shown only in staff view (privacy rule still enforced)
   - Deferred donors show specific reason (age, weight, donation gap)

4. **Experiment Mode** (`/staff/experiment` GET/POST)
   - Compare two alerting strategies on synthetic donor pool:
     - **Broadcast:** Alert entire pool at once (one 10-minute window)
     - **Waves:** Wave 1 (top 10 by score), check at 10 min, Wave 2 (next 20) if needed (20 min total)
   - Inputs: pool size, units needed, trials (default 20), seed
   - For each trial:
     - Generate synthetic donors with random `predicted_score` (0-1)
     - Simulate both strategies with same seeded RNG (deterministic)
     - Count alerts sent, time to fulfill (in 10-min windows), success rate
   - Output: per-strategy averages in table + CSS bar charts
   - **Key insight:** Waves strategy consistently sends fewer alerts than Broadcast (donor privacy benefit)

5. **Updated Test Suite** 
   - Stage 4 tests (4 updated) to verify-first workflow:
     - `test_activation_writes_wave1_alerts` — now verifies first
     - `test_request_status_changes_to_active` — multi-step (pending → verified → active)
     - `test_activation_fails_on_unverified_request` — 409 conflict
     - `test_reject_workflow` — new test for reject path
   - Stage 5 tests (9 new):
     - `TestVerificationWorkflow` (4 tests): verify status, reject status, audit log, activation requires verify
     - `TestStaffDashboard` (2 tests): request grouping by status, donor directory fields
     - `TestExperimentMode` (3 tests): determinism, waves < broadcast in alert count, success rates valid

### Test Coverage

**Total: 85 tests passing**
- Stage 1: 18 tests
- Stage 2: 27 tests
- Stage 3: 11 tests
- Stage 4: 17 tests (4 updated for verify-first, 3 new)
- Stage 5: 9 new tests
- **+1 new test** in Stage 1 for security flag enforcement

**Backward Compatibility:**
- All 76 tests from Stages 1-4 still passing
- Updated /staff route to require ?staff=1 (security)
- Stage 1 test updated to pass staff flag; new test verifies 403 without it

### Key Files Modified

| File | Changes |
|------|---------|
| `app.py` | Added verify, reject, staff dashboard, donor directory, experiment mode routes (5 new routes) |
| `db.py` | Added `update_request_status`, `verify_request`, `reject_request`, `get_requests_by_status`, `get_all_donors` |
| `tests/mock_db.py` | Added same functions as db.py for testing |
| `tests/test_stage1.py` | Updated /staff test to use ?staff=1; added test for 403 without flag |
| `tests/test_stage4.py` | Updated 4 activation tests for verify-first workflow; added reject test |
| `tests/test_stage5.py` | NEW: 9 comprehensive tests for all Stage 5 features |
| `BLOODBEACON_STATUS.md` | Added Stage 5 section |

### Technical Decisions

1. **Verify-first workflow is STRICT:** Activation now requires `status="verified"`, returning 409 Conflict if caller tries to activate pending requests. Enforces explicit staff review step.

2. **Staff flag (?staff=1) on all POST endpoints:** Returns 403 without flag. Prevents accidental non-staff access; can be replaced with session-based auth in Stage 6.

3. **Seeded RNG per trial in experiment:** Each trial uses `Random(seed + trial_index)` for reproducible comparisons while varying slightly across trials.

4. **Experiment output is averages only:** No raw per-trial data shown (avoids noise). Summary shows: avg alerts sent, avg time (in 10-min windows), avg success rate per strategy.

5. **Donor directory filters at app level:** No database queries filtered (mock_db doesn't support WHERE clauses); Python does the filtering. Real DB version would push to Supabase.

### Assumptions & Future Enhancements

- Experiment runs in-request (no background jobs; max ~20 trials × pool_size is fast enough)
- Seed parameter is per-experiment (not per-trial auto-increment; user can specify)
- Staff dashboard doesn't auto-refresh (user clicks Refresh); real version could use polling/WebSockets
- "Close request" functionality not yet implemented (button present, logic in Stage 6)
- Experiment assumes 10-minute windows between waves (hardcoded, not configurable)

### Verified Behavior

✅ Verify-first enforcement: Attempting to activate pending_verification request returns 409  
✅ Reject audit trail: Rejected requests logged with reason  
✅ Staff flag security: All POST endpoints return 403 without ?staff=1  
✅ Dashboard status grouping: Requests appear under correct status bucket  
✅ Donor eligibility badges: Deferred donors show reason; eligible donors show badge  
✅ Experiment determinism: Same seed always produces same averages  
✅ Experiment correctness: Waves alerts ≤ Broadcast alerts; success rates ∈ [0,1]  
✅ All previous tests still passing: 100% backward compatibility

---

## Stage 5.1: Experiment Routes Proven + Close Request

**Objective:** Implement and test Flask route handlers for experiment mode with UI templates, add close request functionality, and verify dashboard template rendering.

**Status:** ✅ COMPLETE (10 new tests, 95 total passing)

### What Was Built

1. **Experiment Mode Templates**
   - `experiment_mode.html`: Form for pool size, units needed, trials, seed (GET endpoint)
   - `experiment_results.html`: Results display with:
     - Per-strategy metrics (avg alerts, avg time, success rate)
     - CSS bar charts for visual comparison
     - Synthetic data caption (required by spec)
     - Parameters section showing inputs

2. **Close Request Endpoint** (`/request/<id>/close` POST)
   - Closes active or verified requests only
   - Records staff name and reason in audit log
   - Returns 403 without ?staff=1 flag
   - Status transition: verified/active → closed

3. **Dashboard Template Update** (`staff_dashboard.html`)
   - Renders requests grouped by status (pending_verification, verified, active, fulfilled, rejected)
   - Shows patient name, hospital, city, blood group, status badge for each request
   - Counts requests per status bucket
   - Fixed to use `requests_by_status` dict instead of flat list

4. **New Test Coverage** (10 tests, all passing)
   - **Experiment Routes Tests (6):**
     - GET returns 200 with form fields
     - POST deterministic: same seed twice → identical results
     - Waves ≤ Broadcast (alert count)
     - Success rates valid in [0, 1]
     - Results page shows synthetic data caption
     - 403 without ?staff=1 flag
   - **Close Request Tests (3):**
     - Close active request changes status
     - Close verified request works
     - Close creates audit log entry with staff name and reason
   - **Dashboard Render Tests (1):**
     - Dashboard renders all requests grouped by status
     - All patient names appear in response

### Key Implementation Details

1. **Experiment Determinism:** Both runs with seed=42 produce exact floating-point matches for avg alerts (proven by test parsing HTML output and comparing strings).

2. **Waves vs Broadcast Logic:**
   - Broadcast: Alert all donors in 1 wave (10-min window)
   - Waves: Alert top 10 first, then next 20 if needed (up to 20-min window)
   - Waves consistently sends fewer or equal alerts than Broadcast

3. **Close Request Validation:** Can only close requests in `active` or `verified` status (not pending, fulfilled, or rejected).

4. **Mock DB Patching:** Tests patch `sys.modules['db'] = mock_db` BEFORE importing app to ensure Flask uses mock DB.

5. **Dashboard Grouping:** Python dict with status buckets; template iterates per-status using `for status, reqs in requests_by_status.items() if reqs` to show only non-empty statuses.

### Verified Behavior

✅ Experiment GET returns 200 with form  
✅ Experiment POST determinism: same seed → identical averages  
✅ Waves alert count ≤ Broadcast (privacy benefit)  
✅ Success rates always 0.0 or 1.0 (in valid range)  
✅ Results page shows synthetic data caption  
✅ Close request endpoint requires staff flag (403 without)  
✅ Close creates audit log with actor/action/reason  
✅ Dashboard renders all status groups with patient names  
✅ All 95 tests passing (85 previous + 10 new)  
✅ 100% backward compatibility maintained

### Files Modified

| File | Changes |
|------|---------|
| `templates/experiment_mode.html` | NEW: Form for experiment parameters |
| `templates/experiment_results.html` | NEW: Results display with metrics, bars, synthetic caption |
| `templates/staff_dashboard.html` | Updated to render requests_by_status dict with grouping |
| `app.py` | Added /request/<id>/close route; no changes to existing logic |
| `db.py` | Added close_request() function |
| `tests/mock_db.py` | Added close_request() and get_audit_log() functions |
| `tests/test_stage5.py` | Added 10 new tests (Experiment Routes, Close Request, Dashboard Render); fixed imports for mock_db patching |
| `BLOODBEACON_STATUS.md` | Added Stage 5.1 section |

---

**Last Updated:** 2024-11-10  
**Stages Complete:** Stage 1 ✅, Stage 2 ✅, Stage 2.1 ✅, Stage 3 ✅, Stage 4 ✅, Stage 5 ✅, Stage 5.1 ✅, Stage 6 ✅
**Total Tests:** 106 passing (18 + 27 + 11 + 17 + 9 + 10 + 11 + 1 flag test; plus 3 bridge npm tests)
**Commits:**
  - Stage 2: `eligibility + compatibility engines, match preview upgrade`
  - Stage 2.1: `plasma matrix correction + RBC table test`
  - Stage 3: `donor response predictor`
  - Stage 4: `wave alerting + simulator`
  - Stage 5: `staff dashboard + experiment mode`
  - Stage 5.1: `experiment routes proven + close request`
  - Stage 6: `WhatsApp bridge + deploy + hardening`

---

## Stage 6: WhatsApp Bridge + Deployment (COMPLETE) ✅

### Objective

Integrate real WhatsApp messaging via Baileys library; build deployment-ready Flask app with gunicorn; implement message deduplication, reconnection logic, and hardening checks.

### What Was Built

**1. WhatsApp Bridge (Node.js)**

- **Directory:** `whatsapp-bridge/`
- **Entry Point:** `index.js` — Initializes Baileys socket, lifecycle manager, HTTP API server
- **Lifecycle Management (`lifecycle.js`):**
  - Connection state tracking (connecting, connected, authenticating, authenticated)
  - Graceful disconnect handling
  - Auto-reconnect on transient errors (delay, disconnected, restoring, etc.)
  - **No auto-reconnect on loggedOut status** (terminal state; requires manual QR re-scan)
  - Message handler: processes both 'notify' (new) and 'append' (history) upserts
  - Deduplication: tracks processed message IDs in `StateStore`

- **Message Handling (`messages.js`):**
  - Receives WhatsApp messages; checks for duplicate message_id
  - Posts confirmed replies to Flask `/internal/whatsapp-reply` endpoint
  - 30-second timeout; passes `X-Bridge-Secret` header for authentication
  - Bridge HTTP API server: 
    - `GET /status` — Returns `{"status": "connected|disconnected"}` 
    - `POST /send` — Sends message to phone via Baileys (`{phone, message}`)
  - Requires `X-Bridge-Secret` header validation

- **State Persistence (`state.js`):**
  - Persists message IDs to `bridge-state.json` for idempotency across restarts
  - Implements `StateStore` interface for Baileys
  - Loads/saves on each message processed

- **Configuration (`package.json`):**
  - Dependencies: `@whiskeysockets/baileys`, `axios`, `express`, `dotenv`
  - Node.js >=20 required
  - Test runner: built-in Node test framework

- **Tests (`test/bridge.test.js`):**
  - ✅ Message dedupe: same ID processed once
  - ✅ Reconnect logic: retry on transient error, not on loggedOut
  - ✅ No reconnect on loggedOut status (terminal)

**2. Flask WhatsApp Integration**

- **Health Endpoint (`GET /health`)**
  - Returns `{"ok": true}` for deployment monitoring

- **Reply Handler (`POST /internal/whatsapp-reply`)**
  - Required header: `X-Bridge-Secret` (401 if mismatch)
  - Payload: `{phone, text, message_id}`
  - Logic:
    1. Lookup donor by phone; if not found → return 200 (idempotent)
    2. Check message_id against all donor alerts (dedupe); if seen → return 200
    3. Find first pending alert (reply = None) for donor
    4. Map text: "1"→confirmed, "2"→donated_recently, "3"→declined
    5. Invalid reply → send re-ask via bridge, return 200
    6. Record reply in alert, mark showed_up = true
    7. If "2" (donated_recently) → insert self-report donation (source="self_report", units=1)
    8. Recount confirmed alerts for request; if units met → mark "fulfilled", log audit entry
    9. (Stub) Fire Wave 2 if Wave 1 exhausted but not fulfilled
  - Always returns 200 for idempotency (failed bridge calls don't block reply processing)

**3. Deployment Configuration**

- **`Procfile`:** `web: gunicorn app:app` (Heroku/Render standard)
- **`render.yaml`:** Render-specific build/run config
- **`requirements.txt` Updates:**
  - `requests==2.32.3` (Flask → Bridge HTTP calls)
  - `gunicorn==23.0.0` (production WSGI server)

- **`.env.example` Updates:**
  - `BRIDGE_URL=http://127.0.0.1:3100` (Bridge API server; localhost only)
  - `BRIDGE_SECRET=your-secret-key-here` (Shared with bridge via env)
  - `FLASK_URL=http://localhost:5001` (Bridge posts to this URL)

**4. Testing & Hardening**

- **Flask WhatsApp Tests (`tests/test_stage6.py`):**
  - ✅ 11 tests covering:
    - Health endpoint returns 200
    - Secret validation (401 without/wrong header)
    - Unknown phone handled idempotently
    - Reply "1" marks alert confirmed
    - Reply "2" inserts self-report donation
    - Reply "3" marks alert declined
    - Message_id dedupe (same ID processed once)
    - Invalid reply triggers re-ask (logic, not bridge call)
    - Request fulfillment when units met
  - All tests use mock_db (no live connection)

- **Hardening Checks:**
  - ✅ `git ls-files` — No .env in repo
  - ✅ Code scan — No hardcoded BRIDGE_SECRET, SUPABASE_URL, keys
  - ✅ Phone number logging — Only in error logs (acceptable for debugging)
  - ✅ Backward compatibility — All 106 tests pass (95 previous + 11 new)

### Key Design Decisions

1. **Baileys Lifecycle Pattern:**
   - Follows FirstcallAI proven approach: factory + event handlers + separate lifecycle
   - Auto-reconnect only on transient errors; loggedOut is terminal
   - Exponential backoff stub (currently 5s linear; can be enhanced)

2. **Message Deduplication:**
   - Tracks message IDs in StateStore (persisted to bridge-state.json)
   - Both 'notify' (new) and 'append' (history) upserts processed
   - Second upsert of same ID skipped
   - Critical for idempotency when bridge restarts

3. **Flask Reply Endpoint Idempotency:**
   - Always returns 200 (bridge can safely retry failed calls)
   - Silent success for unknown phones (no side effects)
   - Message_id tracked in alert record; dedupe check compares against all alerts for donor
   - No exception thrown; malformed requests logged but don't crash

4. **Self-Report Donations:**
   - Inserted with `source="self_report"` when donor replies "2"
   - Flows into Stage 2 eligibility engine (triggers cooldown deferrals)
   - Units always 1; donated_on set to today (no admin override)

5. **Localhost-Only Bridge:**
   - `BRIDGE_URL=http://127.0.0.1:3100` (default)
   - Flask can access; external internet cannot
   - Protects against bridge DoS/abuse

### Files Modified/Created

**New Files:**
- `whatsapp-bridge/` directory (complete Node.js bridge)
  - `index.js`, `lifecycle.js`, `messages.js`, `state.js`
  - `package.json`, `package-lock.json`
  - `.gitignore`, `README.md`
  - `test/bridge.test.js`

- `tests/test_stage6.py` — 11 Flask WhatsApp tests

**Modified Files:**
- `app.py` — Added `/health` and `/internal/whatsapp-reply` endpoints
- `requirements.txt` — Added requests, gunicorn
- `.env.example` — Added BRIDGE_URL, BRIDGE_SECRET, FLASK_URL
- `tests/mock_db.py` — Fixed `get_alerts_for_donor()`, enhanced `update_alert_reply()` with message_id storage
- `Procfile` — New (deployment)
- `render.yaml` — New (deployment)
- `LIVE_TEST.md` — Manual two-phone test script (not automated)

### Verified Behavior

✅ `/health` returns 200 with `{"ok": true}`  
✅ `/internal/whatsapp-reply` requires secret header (401 without)  
✅ Unknown phone number returns 200 (idempotent)  
✅ Reply "1" marks alert confirmed  
✅ Reply "2" inserts self-report donation  
✅ Reply "3" marks alert declined  
✅ Message_id deduplication works (same ID → already_processed)  
✅ Invalid reply (not 1/2/3) triggers re-ask  
✅ Request fulfillment when units met  
✅ Bridge message dedupe (same message ID skipped on restart)  
✅ Bridge reconnect on transient errors (not on loggedOut)  
✅ All 106 Flask tests pass (95 previous + 11 new)  
✅ All 3 bridge npm tests pass  
✅ 100% backward compatibility maintained

### Test Counts

- **Flask Tests:** 106 total (95 + 11 new)
  - Stage 1: 18
  - Stage 2: 27
  - Stage 3: 11
  - Stage 4: 17
  - Stage 5: 9
  - Stage 5.1: 10
  - Stage 6: 11
  - Flag test: 1

- **Bridge Tests:** 3 (Node.js test runner)
  - Message dedupe
  - Reconnect on transient
  - No reconnect on loggedOut

---

## Stage 6.1: WhatsApp Outbound Path (COMPLETE) ✅

### Objective

Prove the WhatsApp outbound path: Wave 1 alerts written with channel="whatsapp", Flask calls bridge `POST /send` for each donor; Wave 2 fires on WhatsApp if Wave 1 exhausted; staff request page shows bridge status (connected/not connected).

### What Was Built

**1. WhatsApp Activation**

- **Updated `activate_request()` function:**
  - Accepts `?channel=whatsapp` parameter (defaults to "whatsapp")
  - Writes Wave 1 alerts with channel=whatsapp
  - Calls `_send_whatsapp_alert()` helper for each donor
  - Helper constructs message and POSTs to bridge `/send` with X-Bridge-Secret header

- **Message Format:**
  - `"BloodBeacon: {blood_group} blood needed at {hospital_name}. Reply 1 (I can donate), 2 (I donated recently), or 3 (Not now)."`
  - Personalized per request; sent to donor phone

**2. Wave 2 on WhatsApp**

- **Updated `advance_simulation()` function:**
  - Retrieves Wave 1 channel from existing alerts
  - When Wave 1 exhausted below target units, fires Wave 2 with same channel
  - If channel="whatsapp", calls `_send_whatsapp_alert()` for each Wave 2 donor
  - Audit log notes channel: `"Wave 1 had X confirmations, firing Wave 2 with Y donors on whatsapp"`

**3. Bridge Status Display**

- **New `_get_bridge_status()` function:**
  - Calls bridge `GET /status` endpoint
  - Returns "connected" if 200, else "not connected"
  - Gracefully handles connection errors (5s timeout)

- **Updated `request_status()` route:**
  - Calls `_get_bridge_status()` in staff mode only
  - Passes `bridge_status` to template

- **Updated `request_status.html` template:**
  - Shows bridge status line in staff mode when request is active
  - Green for "connected", red for "not connected"
  - Format: `WhatsApp Bridge: Connected | Not Connected`

**4. Testing & Verification**

- **Flask WhatsApp Activation Tests (3 tests):**
  - ✅ `test_activation_with_whatsapp_sends_messages`: Mocks requests.post, verifies calls with correct payload and secret header
  - ✅ `test_activation_creates_whatsapp_alerts`: Confirms alerts created with channel="whatsapp"
  - ✅ `test_activation_default_channel_is_whatsapp`: Default channel is whatsapp (no explicit ?channel= needed)

- **Flask Wave 2 Tests (2 tests):**
  - ✅ `test_wave2_inherits_whatsapp_channel`: Wave 2 inherits channel from Wave 1
  - ✅ `test_wave2_messages_sent_on_whatsapp`: Wave 2 fires /send calls when needed

- **Bridge Status Tests (3 tests):**
  - ✅ `test_bridge_status_shown_when_connected`: Status "connected" shown in staff view when bridge responds
  - ✅ `test_bridge_status_degraded_when_down`: Status "not connected" shown when bridge down/unreachable
  - ✅ `test_bridge_status_not_shown_in_public_view`: Status hidden in non-staff public view

### Verified Behavior

✅ Wave 1 activation writes alerts with channel=whatsapp  
✅ Flask calls bridge POST /send once per Wave 1 donor  
✅ Message payload includes blood group and hospital name  
✅ X-Bridge-Secret header present and validated  
✅ Wave 2 alerts inherit WhatsApp channel from Wave 1  
✅ Wave 2 fires /send calls to bridge when Wave 1 exhausted  
✅ Staff request page displays bridge status line  
✅ Bridge status degrades gracefully when down  
✅ Bridge status hidden in public view (non-staff)  
✅ All 114 tests pass (106 previous + 8 new)  
✅ 100% backward compatibility maintained  
✅ Bridge npm tests still pass (3/3)

### Files Modified

| File | Changes |
|------|---------|
| `app.py` | Added `_get_bridge_status()` function; updated `request_status()` to pass bridge_status to template; updated `activate_request()` to accept `?channel=` parameter and call `_send_whatsapp_alert()`; added `_send_whatsapp_alert()` helper; updated `advance_simulation()` to inherit channel and send Wave 2 messages |
| `templates/request_status.html` | Added bridge status line (staff view, active status only) showing "Connected / Not Connected" |
| `tests/test_stage61.py` | NEW: 8 comprehensive tests covering activation, Wave 2, and bridge status display (all mocked HTTP calls) |
| `tests/mock_db.py` | Added `_test_staff` dict; updated `reset()` to clear staff; added `insert_staff()` and `get_staff()` functions; fixed alert `created_at` to use date format for alerting.py parsing; updated `update_alert_reply()` to accept optional message_id parameter |

### Design Decisions

1. **Default Channel = WhatsApp:**
   - `?channel=whatsapp` is default; simulator mode requires explicit `?channel=simulator`
   - Reflects production use case (real deployments use WhatsApp)

2. **Bridge Calls in Flask (Not Bridge Itself):**
   - Flask activation/Wave 2 logic calls bridge /send directly
   - Bridge remains stateless message receiver/relay
   - Separates concerns: Flask orchestrates timing, bridge handles messaging

3. **Graceful Status Fallback:**
   - If bridge unreachable, returns "not connected" (no exception thrown)
   - 5-second timeout prevents blocking staff page load
   - Staff can still see request details even if bridge down

4. **Message Format Simple & Clear:**
   - Includes blood group, hospital name, reply options (1/2/3)
   - No donor identifiers in message (privacy)
   - Donor phone matched via WhatsApp routing

### Test Counts

- **Flask Tests:** 114 total (106 + 8 new)
  - Stage 1: 18
  - Stage 2: 27
  - Stage 3: 11
  - Stage 4: 17
  - Stage 5: 9
  - Stage 5.1: 10
  - Stage 6: 11
  - Stage 6.1: 8
  - Flag test: 1

- **Bridge Tests:** 3 (Node.js test runner)
  - Message dedupe
  - Reconnect on transient
  - No reconnect on loggedOut

---

## Stage 6.1.1: Staff UX Mini-Fix

**Objective:** Replace blank 403 errors with friendly HTML, implement staff session persistence, verify approval flow end-to-end, and fix display formatting.

**Status:** ✅ COMPLETE

### What Was Built

1. **Friendly 403 Error Pages**
   - ✅ Created `templates/staff_required.html` with styled error message
   - ✅ Message: "Staff access — add ?staff=1 to the address"
   - ✅ All 9 staff-only routes now return friendly HTML instead of blank 403
   - ✅ HTTP status remains 403 for proper semantics

2. **Staff Session Persistence**
   - ✅ Added `is_staff()` helper that checks both `?staff=1` flag AND session
   - ✅ When `?staff=1` is passed, `session["staff"] = True` is set
   - ✅ Subsequent requests can use session without flag
   - ✅ All staff routes accept either method

3. **Approval Flow (Verify/Reject)**
   - ✅ Added Verify and Reject buttons to pending_verification requests
   - ✅ Buttons render on `/request/<id>?staff=1` when status = pending_verification
   - ✅ Forms POST to `/request/<id>/verify?staff=1` and `/request/<id>/reject?staff=1`
   - ✅ Verify flips status to "verified" and creates audit entry
   - ✅ Reject flips status to "rejected" and creates audit entry with reason
   - ✅ Both require staff access (friendly 403 if missing)

4. **Display Formatting**
   - ✅ Added `human_date` Jinja2 filter: converts ISO dates/timestamps to "10 Nov 2026, 10:55 PM"
   - ✅ Added `unit_int` Jinja2 filter: renders 2.0 as "2", not "2.0"
   - ✅ Applied to request_status.html: "Needed By" and "Units" fields
   - ✅ Handles both ISO date (2026-11-10) and ISO timestamp (2026-11-10T22:55:00Z) formats

5. **Staff Links**
   - ✅ Home page staff link carries `?staff=1`
   - ✅ Staff dashboard "View Details" links carry `?staff=1`
   - ✅ All staff links maintain flag through navigation

### Test Coverage

- **New Tests:** 20 comprehensive tests in `test_stage61_1_staff_ux.py`
  - 3 tests for friendly 403 pages (staff dashboard, donors, activate)
  - 1 test for session persistence
  - 9 tests for approval flow (buttons, forms, status flip, audits, permission checks)
  - 4 tests for date/unit formatting
  - 2 tests for staff link flags
  - 2 tests for backward compatibility

- **All Previous Tests:** 114 tests still passing
  - Total: **134 tests passing** (114 + 20 new)
  - ✅ 100% backward compatibility maintained

### Files Created

| File | Purpose |
|------|---------|
| `templates/staff_required.html` | Friendly 403 error page with styled message |
| `tests/test_stage61_1_staff_ux.py` | 20 new tests for staff UX improvements |

### Files Modified

| File | Changes |
|------|---------|
| `app.py` | Added `session` import; added `human_date` and `unit_int` Jinja2 filters; added `is_staff()` and `require_staff()` helpers; updated all 9 staff-only routes to use `require_staff()` instead of blank 403 |
| `templates/home.html` | Changed staff link from `/staff` to `/staff?staff=1` |
| `templates/staff_dashboard.html` | Changed "View Details" link from `/request/<id>` to `/request/<id>?staff=1` |
| `templates/request_status.html` | Added Verify/Reject forms for pending_verification; applied `human_date` filter to "Needed By"; applied `unit_int` filter to "Units" |

### Design Decisions

1. **Session Persistence Pattern:**
   - Flag `?staff=1` sets session; future requests use session
   - Simpler than re-passing flag through every link
   - Flask's test client handles session correctly

2. **Friendly 403 Reuses Base Template:**
   - `staff_required.html` extends `base.html` for consistent styling
   - Shows the path to add flag (e.g., `/staff?staff=1`)
   - Users see an actual page, not an empty error

3. **Approval Forms Inline:**
   - Verify/Reject buttons on the same request_status page
   - No separate modal/form page needed
   - Forms submit with hidden staff_name; production would capture from session

4. **Date Filter Handles Multiple Formats:**
   - Handles ISO date (2026-11-10) → "10 Nov 2026"
   - Handles ISO datetime (2026-11-10T22:55:00Z) → "10 Nov 2026, 10:55 PM"
   - Returns empty string for None; returns original if parse fails
   - Strips leading zeros from day (01 → 1)

### Verified Behavior

✅ Accessing `/staff` without flag returns 403 with friendly HTML, not blank  
✅ Accessing `/staff?staff=1` shows dashboard (flag sets session)  
✅ Pending requests show Verify and Reject buttons  
✅ Verify flips status to verified + audit entry  
✅ Reject flips status to rejected + audit entry  
✅ POST without staff flag returns friendly 403  
✅ Needed By renders as "10 Nov 2026, 10:55 PM", not "2026-11-10T22:55:00Z"  
✅ Units renders as "2", not "2.0"  
✅ Staff links carry ?staff=1  
✅ All 134 tests passing; full backward compatibility

### Next Steps

Ready for deployment. All staff UX improvements complete and tested.

> **Schema audit lesson:** The mock database accepted `verified_by` as a staff-name
> string even while `schema.sql` declared it `BIGINT`; Supabase had already been
> corrected manually to `TEXT`. The schema is now aligned with the live write path.
> The audit also found that application code writes the `verified` request status,
> so that value is now included in the schema check constraint. All other `BIGINT`
> identifiers and foreign keys match the numeric IDs written by the application.

---

## Two-Step Donor Conversation: Recency First

**Status:** ✅ COMPLETE

WhatsApp and simulator alerts now use the same staged conversation:

1. `awaiting_recency`: asks whether the donor donated in the last three months.
   Reply `1` records a today's `self_report` donation, marks the alert
   `donated_recently`/`done`, sends a thank-you, and ends the conversation.
   Reply `2` advances to `awaiting_confirm`.
2. `awaiting_confirm`: asks whether the donor can come to the hospital.
   Reply `1` records `confirmed` and runs the existing fulfilment/number-reveal
   rules. Reply `2` records `declined` and ends the conversation.
3. Unclear text re-asks the current step without advancing the stage.

The alert schema and mock now include `stage` values
`awaiting_recency`, `awaiting_confirm`, and `done`; message IDs remain
deduplicated. The former single-step `1 = confirmed, 2 = donated_recently,
3 = declined` mapping was removed because it conflated recency screening with
availability. `LIVE_TEST.md` documents the revised real-device script.

**Verification:** 137 Flask tests pass, including the two-step happy path,
recency deferral through the eligibility engine, Step 2 decline, unclear-text
re-asks, and simulator parity.

---

## India/Nepal Phone Country Picker

Donor registration now requires a country selection (India `+91`, selected by
default, or Nepal `+977`) and a 10-digit national mobile number. The shared
`normalize_phone(country, national)` helper strips punctuation, removes a
pasted matching country code, validates the national length, and stores only
digits in international format. The bridge applies the same digits-only
defence before constructing WhatsApp JIDs and inbound matching compares
digits-only values for legacy records.

This closes a live-test failure where a stored `+977...` value produced an
invalid WhatsApp JID and the alert disappeared. Focused Python coverage and
bridge tests verify India, Nepal, pasted country-code input, short-number
rejection, and JID normalization.

---

## WhatsApp Registration Welcome

After a real donor registration is saved, the app makes one best-effort
`/send` call to the existing bridge using the stored digits-only number. The
message includes the donor's first name, blood group, and city. A successful
send records `welcome_msg_sent`; an offline, timed-out, or failed bridge
records `welcome_msg_failed`. Neither outcome blocks or changes the normal
registration success path. Seed data and test fixtures do not send welcomes.

## Staff Verification to Activation

Staff verification and rejection now return to the staff request detail view.
Verified requests show the WhatsApp bridge status, donor match preview, and
the `Activate — start Wave 1` control; active requests retain wave status,
Advance Wave, and Close Request controls. Public request views do not expose
these staff controls.

## Bridge Inbound Authentication and LID Resolution

The bridge now requires one non-empty `BRIDGE_SECRET` from its environment or
`whatsapp-bridge/.env`, uses that value for both Flask reply posts and the
Flask-to-bridge API, and checks authenticated `GET /internal/ping` at startup.
Inbound Baileys `@lid` identities resolve through `remoteJidAlt`,
`participantAlt`, or `senderPn` before digits-only forwarding; unresolved
identities are forwarded as the raw JID and logged for diagnosis.

The bridge also consults Baileys' LID mapping store and a persisted
`lidToPhone` map in `bridge-state.json`. Successful outbound sends call
`onWhatsApp(phone)` and learn canonical `@lid` identities for future inbound
replies. If no mapping is available, the full inbound message key is logged
before forwarding the raw JID.

## Staff Wave Outcomes and Bridge Status

Activation audit details now aggregate the planner's existing skip reasons and
the staff request page shows the sent/queued/skipped wave outcome, including an
explicit reason when no donors are sent. Staff bridge status checks the
authenticated bridge `/status` endpoint with the shared secret and displays a
brief error when that check fails, rather than reporting an unqualified
connection state.

## Supabase Timestamp Parsing

Supabase `timestamptz` values are accepted by the shared `utils.parse_date`
helper, including date-only strings, fractional seconds, `Z` timestamps,
offset timestamps, and Python date/datetime objects. The activation path now
uses it for donor birth dates and donations in `eligibility.py`, donation and
alert history in `predictor.py`, and alert history in `alerting.py`; the
request display formatter also remains tolerant of full ISO timestamps.
