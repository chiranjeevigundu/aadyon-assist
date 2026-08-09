-- Remove visa / immigration profile fields.
-- Not applicable to a general finance / net-worth app usable by anyone; the
-- "Digital Me" persona (incl. the visa dimension) has been removed from the app.
-- transaction

ALTER TABLE profile
  DROP COLUMN IF EXISTS visa_type,
  DROP COLUMN IF EXISTS visa_status,
  DROP COLUMN IF EXISTS work_auth_until;
