# BloodBeacon Deployment Checklist

| Variable | Where its value lives |
| --- | --- |
| `SUPABASE_URL` | Supabase dashboard → Project Settings → Data API → Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase dashboard → Settings → API Keys → rotated secret/service-role key |
| `BRIDGE_URL` | Leave empty now; after starting cloudflared, use its public HTTPS tunnel URL |
| `BRIDGE_SECRET` | The same private value in my local BloodBeacon `.env` and laptop bridge environment |
| `STAFF_PASSCODE` | A private passcode I choose for `/staff` login |
| `SECRET_KEY` | A private random Flask session secret I generate and keep only in local/Render environments |

1. Supabase dashboard → Settings → API Keys → rotate the service key → update my local `.env` myself; nobody else sees the value.
2. Render dashboard → New → Blueprint → select the private `Blood-Beacon`/bloodbeacon repo → Apply → when prompted, paste each environment value using the table above → leave `BRIDGE_URL` empty for now.
3. Wait for **Live** → open the `.onrender.com` URL → register a test donor → submit a test request → confirm the site works (WhatsApp rows show **FAILED**, expected until step 4) → confirm `/staff` passcode login works.
4. WhatsApp phase → with the laptop bridge running on port 3100, run `cloudflared tunnel --url http://localhost:3100` → set Render `BRIDGE_URL` to the printed HTTPS tunnel URL → in `whatsapp-bridge/index.js`, the deployed Flask callback is controlled by environment variable `FLASK_URL` (read into constant `flask`), so restart from `whatsapp-bridge` with `FLASK_URL=https://YOUR-SERVICE.onrender.com BRIDGE_SECRET=YOUR_EXISTING_BRIDGE_SECRET node index.js` → against the deployed site test the full flow: welcome → request → buzz → reply `2` → reply `1` → **Fulfilled**; WhatsApp needs my laptop on, while the website remains available 24×7 regardless.
