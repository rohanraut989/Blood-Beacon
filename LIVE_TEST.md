# BloodBeacon Stage 6 Live Test Script

This script demonstrates a two-phone end-to-end test of the WhatsApp bridge integration. **Do not use your personal WhatsApp account; use a demo/spare number only.**

## Prerequisites

1. **Two WhatsApp accounts:**
   - **Hospital Phone:** Your personal/work number (where you act as hospital staff)
   - **Donor Phone:** A spare/demo number (where you act as the donor replying)

2. **Running Services:**
   - Flask app: `python app.py` on port 5001
   - WhatsApp bridge: `cd whatsapp-bridge && node index.js` on port 3100
   - Bridge env: `FLASK_URL=http://localhost:5001`, `BRIDGE_SECRET=test-secret`

3. **Database Setup:**
   - Supabase project with BloodBeacon schema (all tables RLS enabled)
   - Env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `BRIDGE_SECRET`

## Test Flow

### Step 1: Seed a Donor (Hospital Phone)

1. Open BloodBeacon home: `http://localhost:5001/`
2. Click **Register** and fill out donor form:
   - Name: (anything)
   - Phone: **The donor phone number** (e.g., +917987654321)
   - Blood Group: O+
   - City: Kathmandu
   - Other fields: defaults
3. Submit. Note the donor ID from the next page.

### Step 2: QR-Login the Bridge (Donor Phone)

1. Terminal running the bridge should show a QR code.
2. On the **donor phone**, open WhatsApp.
3. Go to **Settings > Linked Devices > Link a device**.
4. Scan the QR from the bridge terminal.
5. Wait for "BloodBeacon WhatsApp bridge is listening" message in terminal.

### Step 3: Create a Blood Request (Hospital Phone)

1. Go to `http://localhost:5001/` on hospital phone.
2. Click **Request** and fill:
   - Patient Name: (any)
   - Blood Group: O+ (match donor)
   - Hospital Name: Test Hospital
   - City: Kathmandu (match donor)
   - Units Needed: 2
   - Needed By: (date 5 days away)
3. Submit. Note the request ID.

### Step 4: Staff Verification & Activation (Hospital Phone)

1. Go to Staff Dashboard: `http://localhost:5001/staff?staff=1`
2. Find the request in **Pending Verification** section.
3. Click **View Details**.
4. Click **Verify Request** (buttons for staff actions).
5. After verified, click **Activate Request**.
6. **Choose Channel:** Select `whatsapp` (not simulator).
7. Click **Send Alerts**.

### Step 5: Bridge Sends Wave 1 Alert (Automatic)

- The bridge should immediately POST to Flask `/internal/whatsapp-reply` handler.
- **Donor phone** receives: *"BloodBeacon: O+ blood needed at Test Hospital, Kathmandu by [DATE]. Reply 1 = I can donate, 2 = I donated recently, 3 = Not now."*

### Step 6: Donor Replies (Donor Phone)

**Test Case A: Donor Can Contribute (Reply "1")**

1. On donor phone, reply to the BloodBeacon message with: `1`
2. Wait ~5 seconds.
3. Go to request details page (hospital phone).
4. Click **Refresh** or reload.
5. **Verify:**
   - Alert status shows "confirmed"
   - Dashboard counter increments
   - If 2 units confirmed, request shows "Fulfilled" ✅

**Test Case B: Donor Donated Recently (Reply "2")**

1. Create a **second request** (same as Step 3).
2. Verify and activate on whatsapp.
3. Donor replies with: `2`
4. Wait ~5 seconds.
5. **Verify:**
   - Alert status shows "donated_recently"
   - Donor enters **cooldown** (next login shows "Deferred until [date]")
   - On the **donor's profile** (staff view), eligible badge changes to "Deferred"
   - If trying to request from this donor again, they appear ineligible

**Test Case C: Invalid Reply → Re-ask**

1. Create a third request, activate on whatsapp.
2. Donor replies with: `xyz` (invalid).
3. Wait ~10 seconds.
4. Donor receives another message: *"BloodBeacon: please reply 1 (I can donate), 2 (I donated recently), or 3 (Not now)."*
5. Donor replies with: `3` (declined).
6. **Verify:**
   - Alert status shows "declined"
   - Request not fulfilled (awaits Wave 2 or manual override)

### Step 7: Check Dashboard & History (Hospital Phone)

1. Go to `/staff?staff=1` dashboard.
2. Check the **Donor Directory** (`/staff/donors?staff=1`):
   - Find the seeded donor.
   - Verify eligibility badge shows:
     - "Eligible" after replying "1" to other requests
     - "Deferred until [DATE]" after replying "2" (cooldown applied)
3. Check **Request Details:**
   - Wave 1 shows all alerts with reply status (confirmed/declined/donated_recently).
   - Audit log shows:
     - `whatsapp_donor` action `request_fulfilled` if enough confirmations
     - `whatsapp_donor` action with reply text recorded

### Step 8: Bridge Reconnect Test (Optional)

1. Stop the bridge: `^C` in bridge terminal.
2. Wait 5 seconds.
3. Bridge terminal shows: *"Reconnecting in 5 seconds"* and then *"BloodBeacon WhatsApp bridge is listening"*.
4. **Verify:** No QR scan required (connection restored).

### Step 9: Check /health Endpoint (Optional)

```bash
curl http://localhost:5001/health
# Expected: {"ok":true}

curl http://127.0.0.1:3100/status \
  -H "X-Bridge-Secret: test-secret"
# Expected: {"connected":true}
```

## Summary of Verified Behaviors

- ✅ Donor seeded with correct phone and blood group
- ✅ Bridge QR scan links spare number
- ✅ Staff can verify and activate on WhatsApp channel
- ✅ Wave 1 alerts sent via WhatsApp
- ✅ Donor replies "1" → alert confirmed, request shows progress
- ✅ Donor replies "2" → donation logged, cooldown applied
- ✅ Donor replies "3" → alert declined, awaits Wave 2
- ✅ Invalid reply → polite re-ask, one re-attempt
- ✅ Request fulfilled when units met
- ✅ Audit log captures all WhatsApp actions
- ✅ Donor directory shows updated eligibility badges
- ✅ Bridge auto-reconnects on transient failure
- ✅ /health and bridge /status endpoints working

## Cleanup

After testing:

```bash
# Clear bridge auth (for fresh QR login next time)
rm -rf whatsapp-bridge/.baileys_auth
rm whatsapp-bridge/bridge-state.json

# Optional: delete test donors/requests from Supabase console
```

---

**Note:** This test uses real WhatsApp accounts and sends real messages. Do not run against production numbers or personal accounts. Always use demo/spare numbers for testing.
