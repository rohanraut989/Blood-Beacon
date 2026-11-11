-- BloodBeacon Schema
-- Run this in the Supabase SQL editor to set up the database

-- donors table
CREATE TABLE IF NOT EXISTS donors (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  blood_group TEXT NOT NULL,
  city TEXT NOT NULL,
  area TEXT,
  phone TEXT NOT NULL UNIQUE,
  gender TEXT,
  date_of_birth DATE,
  weight_kg DECIMAL(5, 2),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_donors_blood_group ON donors(blood_group);
CREATE INDEX IF NOT EXISTS idx_donors_city ON donors(city);
CREATE INDEX IF NOT EXISTS idx_donors_phone ON donors(phone);

-- donations table
CREATE TABLE IF NOT EXISTS donations (
  id BIGSERIAL PRIMARY KEY,
  donor_id BIGINT NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
  donated_on DATE NOT NULL,
  units DECIMAL(5, 2),
  request_id BIGINT,
  source TEXT NOT NULL CHECK (source IN ('self_report', 'whatsapp_reply', 'hospital')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_donations_donor_id ON donations(donor_id);
CREATE INDEX IF NOT EXISTS idx_donations_request_id ON donations(request_id);

-- requests table
CREATE TABLE IF NOT EXISTS requests (
  id BIGSERIAL PRIMARY KEY,
  patient_name TEXT NOT NULL,
  blood_group TEXT NOT NULL,
  component TEXT,
  units DECIMAL(5, 2),
  hospital_name TEXT NOT NULL,
  city TEXT NOT NULL,
  needed_by TIMESTAMP WITH TIME ZONE,
  contact_phone TEXT,
  status TEXT NOT NULL DEFAULT 'pending_verification' CHECK (status IN ('pending_verification', 'verified', 'active', 'fulfilled', 'closed', 'rejected')),
  created_by TEXT NOT NULL CHECK (created_by IN ('public', 'staff')),
  verified_by TEXT,
  match_pool_count INT,
  fulfilled_notified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_requests_blood_group ON requests(blood_group);
CREATE INDEX IF NOT EXISTS idx_requests_city ON requests(city);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);

-- alerts table
CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  request_id BIGINT NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
  donor_id BIGINT NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
  wave_no INT NOT NULL,
  sent_at TIMESTAMP WITH TIME ZONE,
  channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'simulator')),
  match_tier INT NOT NULL DEFAULT 1 CHECK (match_tier IN (1, 2, 3)),
  cross_group BOOLEAN NOT NULL DEFAULT FALSE,
  stage TEXT NOT NULL DEFAULT 'awaiting_recency' CHECK (stage IN ('awaiting_recency', 'awaiting_confirm', 'done')),
  reply TEXT CHECK (reply IN ('confirmed', 'donated_recently', 'declined', 'no_reply', 'passed', 'covered')),
  message_id TEXT,
  replied_at TIMESTAMP WITH TIME ZONE,
  showed_up BOOLEAN,
  close_sent BOOLEAN NOT NULL DEFAULT FALSE,
  receiver_notified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_request_id ON alerts(request_id);
CREATE INDEX IF NOT EXISTS idx_alerts_donor_id ON alerts(donor_id);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS close_sent BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS receiver_notified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS fulfilled_notified BOOLEAN NOT NULL DEFAULT FALSE;

-- rules table (NBTC rulebook)
CREATE TABLE IF NOT EXISTS rules (
  id BIGSERIAL PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO rules (key, value, description)
VALUES ('CASCADE_WINDOW_MINUTES', '2', 'Minutes allowed for each donor conversation question')
ON CONFLICT (key) DO NOTHING;

-- audit_log table
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id BIGINT,
  detail TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity, entity_id);
