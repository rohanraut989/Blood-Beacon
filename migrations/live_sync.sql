-- Idempotent live migration for receiver confirmation and fulfilment notices.
ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS receiver_notified BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE requests
  ADD COLUMN IF NOT EXISTS fulfilled_notified BOOLEAN NOT NULL DEFAULT FALSE;
