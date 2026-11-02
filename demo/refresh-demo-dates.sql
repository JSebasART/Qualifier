-- Move the seeded demo portfolio forward in time, so the case queue looks the
-- way the seed meant it to: a few cases overdue, a few due within two days,
-- applications from 3 hours to 10 days old. Run it the day of (or before) a
-- demo, in the Supabase SQL editor of project jskuoazhcgfyetxrmxyi.
--
-- Needs db migration 20261102000000 (cases.sla_paused_at) applied first.
--
-- Re-runnable: the shift is measured from the data itself (the newest
-- application should be 3 hours old), so a second run moves things ~0.
--
-- What it does not touch: audit_log (append-only by design; the history panels
-- keep their real timestamps, so a seeded case scored "16 oct" can show a
-- history entry from August, and that is the price of an audit log nobody
-- rewrites), ai_usage, profiles, auth. Application numbers stay as they are.
--
-- Five triggers are disabled inside the transaction and re-enabled before it
-- ends; any failure rolls the disabling back too. Otherwise set_updated_at would
-- overwrite the shifted updated_at, clients_audit would write a false "client
-- changed" row per client, and set_document_extracted_at could stamp now().
-- (session_replication_role = replica would be simpler, but the postgres role on
-- Supabase is not allowed to set it: 42501.)
--
-- Only seeded rows should exist. If real QA runs have added rows you want to
-- keep at their real times, add a WHERE clause before running.

DO $$
DECLARE
  delta interval;
  ddays int;
BEGIN
  SELECT (now() - interval '3 hours') - max(created_at) INTO delta FROM applications;
  ddays := round(extract(epoch from delta) / 86400);
  IF delta < interval '1 hour' THEN
    RAISE NOTICE 'Nothing to do: the newest application is already about 3 hours old.';
    RETURN;
  END IF;

  ALTER TABLE public.applications DISABLE TRIGGER applications_set_updated_at;
  ALTER TABLE public.cases        DISABLE TRIGGER cases_set_updated_at;
  ALTER TABLE public.clients      DISABLE TRIGGER clients_set_updated_at;
  ALTER TABLE public.clients      DISABLE TRIGGER clients_audit;
  ALTER TABLE public.documents    DISABLE TRIGGER documents_set_extracted_at;

  UPDATE applications SET created_at = created_at + delta, submitted_at = submitted_at + delta, updated_at = updated_at + delta;
  UPDATE clients      SET created_at = created_at + delta, updated_at = updated_at + delta;
  UPDATE documents    SET uploaded_at = uploaded_at + delta, extracted_at = extracted_at + delta,
    extracted_data = CASE
      WHEN extracted_data ? 'issue_date' AND extracted_data->>'issue_date' ~ '^\d{4}-\d{2}-\d{2}$'
      THEN jsonb_set(extracted_data, '{issue_date}',
                     to_jsonb(to_char((extracted_data->>'issue_date')::date + ddays, 'YYYY-MM-DD')))
      ELSE extracted_data END;
  UPDATE scores        SET created_at = created_at + delta;
  -- sla_paused_at (db 20261102000000) moves with the rest, so a paused case
  -- resumes with the time it actually waited.
  UPDATE cases         SET created_at = created_at + delta, updated_at = updated_at + delta, sla_due_at = sla_due_at + delta,
                           sla_paused_at = sla_paused_at + delta;
  UPDATE case_comments SET created_at = created_at + delta;

  ALTER TABLE public.applications ENABLE TRIGGER applications_set_updated_at;
  ALTER TABLE public.cases        ENABLE TRIGGER cases_set_updated_at;
  ALTER TABLE public.clients      ENABLE TRIGGER clients_set_updated_at;
  ALTER TABLE public.clients      ENABLE TRIGGER clients_audit;
  ALTER TABLE public.documents    ENABLE TRIGGER documents_set_extracted_at;

  RAISE NOTICE 'Shifted by % (issue dates by % days).', delta, ddays;
END $$;

-- Check: expect the newest application ~3 h old, about 4 open cases overdue and
-- 3 due within 48 h, and every issue_date inside its playbook's max_age_days.
-- A case waiting on the applicant is paused, so it counts as neither.
SELECT
  (SELECT round(extract(epoch from now() - max(created_at)) / 3600) FROM applications) AS newest_application_hours,
  (SELECT count(*) FROM cases WHERE status NOT IN ('resolved', 'waiting_on_applicant') AND sla_due_at < now())  AS open_cases_overdue,
  (SELECT count(*) FROM cases WHERE status NOT IN ('resolved', 'waiting_on_applicant') AND sla_due_at >= now()) AS open_cases_on_time,
  (SELECT count(*) FROM cases WHERE status = 'waiting_on_applicant')                                            AS open_cases_paused,
  (SELECT max(extracted_data->>'issue_date') FROM documents)                             AS newest_issue_date;
