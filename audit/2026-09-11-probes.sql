-- Audit probes. Every assertion states the SECURE or CORRECT behaviour, so a
-- `not ok` is a finding. Runs after the CI steps (migrations, seed, grants,
-- real auth.uid()), inside one rolled-back transaction. Each attempt runs as a
-- real `authenticated` session via the same impersonation the repo's suites
-- use, and its error (if any) is printed as a `#` line so a pass can be told
-- apart from a failure for an unrelated reason.
begin;
select plan(12);

-- Fixtures, as the superuser (RLS bypassed): tenants A and B.
insert into tenants (id, name, slug) values
  ('e0000000-0000-0000-0000-000000000001', 'Audit A', 'audit-a'),
  ('f0000000-0000-0000-0000-000000000001', 'Audit B', 'audit-b');
insert into products (id, tenant_id, name, type) values
  ('e0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000001', 'A life', 'life'),
  ('f0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-000000000001', 'B life', 'life');
insert into playbooks (id, tenant_id, product_id, version, status, definition, published_at) values
  ('e0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000002', 1, 'published', '{}', now()),
  ('f0000000-0000-0000-0000-000000000003', 'f0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000002', 1, 'published', '{}', now());
insert into auth.users (id) values
  ('e0000000-0000-0000-0000-00000000000a'),
  ('e0000000-0000-0000-0000-00000000000b'),
  ('e0000000-0000-0000-0000-00000000000c'),
  ('f0000000-0000-0000-0000-00000000000d');
insert into profiles (id, tenant_id, role, full_name) values
  ('e0000000-0000-0000-0000-00000000000a', 'e0000000-0000-0000-0000-000000000001', 'tenant_admin', 'Admin A'),
  ('e0000000-0000-0000-0000-00000000000b', 'e0000000-0000-0000-0000-000000000001', 'underwriter', 'Underwriter A'),
  ('e0000000-0000-0000-0000-00000000000c', 'e0000000-0000-0000-0000-000000000001', 'agent', 'Agent A'),
  ('f0000000-0000-0000-0000-00000000000d', 'f0000000-0000-0000-0000-000000000001', 'underwriter', 'Underwriter B');
insert into applications (id, tenant_id, product_id, applicant_id, status) values
  ('e0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-00000000000a', 'manual_review'),
  ('f0000000-0000-0000-0000-000000000004', 'f0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000002', 'f0000000-0000-0000-0000-00000000000d', 'manual_review');
insert into cases (id, tenant_id, application_id, status) values
  ('e0000000-0000-0000-0000-000000000005', 'e0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000004', 'in_review');

-- Runs `stmt` as `who` under `role_name`, returns the error text or 'no error'.
create function pg_temp.attempt(who uuid, stmt text, role_name text default 'authenticated') returns text
language plpgsql as $$
declare err text;
begin
  perform set_config('request.jwt.claim.sub', coalesce(who::text, ''), true);
  execute format('set local role %I', role_name);
  begin
    execute stmt;
  exception when others then
    err := sqlerrm;
  end;
  execute 'reset role';
  return coalesce(err, 'no error');
end $$;

-- Runs a count query as `who` under `role_name`.
create function pg_temp.count_as(who uuid, q text, role_name text default 'authenticated') returns bigint
language plpgsql as $$
declare n bigint;
begin
  perform set_config('request.jwt.claim.sub', coalesce(who::text, ''), true);
  execute format('set local role %I', role_name);
  execute q into n;
  execute 'reset role';
  return n;
end $$;

-- P1/P2 — privilege escalation through the admin's own profile row.
select '# P1 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000a',
  $$update profiles set role = 'superadmin' where id = 'e0000000-0000-0000-0000-00000000000a'$$);
select is((select role from profiles where id = 'e0000000-0000-0000-0000-00000000000a'), 'tenant_admin',
  'P1 a tenant_admin cannot promote themselves to superadmin');
select is(pg_temp.count_as('e0000000-0000-0000-0000-00000000000a',
  $$select count(*) from applications where tenant_id = 'f0000000-0000-0000-0000-000000000001'$$), 0::bigint,
  'P2 tenant A''s admin still cannot read tenant B''s applications');

-- P3/P4 — scores are the pipeline's output; only the service role should write them.
select '# P3 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000b',
  $$insert into scores (tenant_id, application_id, playbook_id, playbook_version, decision)
    values ('f0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000004', 'f0000000-0000-0000-0000-000000000003', 1, 'approve')$$);
select is((select count(*) from scores where application_id = 'f0000000-0000-0000-0000-000000000004'), 0::bigint,
  'P3 an underwriter in tenant A cannot write a score into tenant B');
select '# P4 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000b',
  $$insert into scores (tenant_id, application_id, playbook_id, playbook_version, decision, final_score)
    values ('e0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000003', 1, 'approve', 99)$$);
select is((select count(*) from scores where application_id = 'e0000000-0000-0000-0000-000000000004'), 0::bigint,
  'P4 an underwriter cannot write the pipeline''s score for their own tenant''s application');

-- P5/P6 — segregation of duties: the intake role deciding a case.
select '# P5 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000c',
  $$update applications set status = 'approved' where id = 'e0000000-0000-0000-0000-000000000004'$$);
select is((select status from applications where id = 'e0000000-0000-0000-0000-000000000004'), 'manual_review',
  'P5 an agent (intake role) cannot approve an application');
select '# P6 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000c',
  $$update cases set status = 'resolved' where id = 'e0000000-0000-0000-0000-000000000005'$$);
select is((select status from cases where id = 'e0000000-0000-0000-0000-000000000005'), 'in_review',
  'P6 an agent cannot resolve a case');

-- P7 — the audit trail's integrity.
select '# P7 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000c',
  $$insert into audit_log (tenant_id, actor_type, action, entity_type, entity_id)
    values ('e0000000-0000-0000-0000-000000000001', 'system', 'application.scored', 'application', 'e0000000-0000-0000-0000-000000000004')$$);
select is((select count(*) from audit_log where entity_id = 'e0000000-0000-0000-0000-000000000004' and actor_type = 'system'), 0::bigint,
  'P7 a staff member cannot write an audit entry attributed to the system');

-- P8/P9 — cross-tenant pointers the service-role pipeline later follows.
select '# P8 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000c',
  $$insert into applications (id, tenant_id, product_id, applicant_id, status, playbook_id, playbook_version)
    values ('e0000000-0000-0000-0000-000000000006', 'e0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-00000000000c', 'draft', 'f0000000-0000-0000-0000-000000000003', 1)$$);
select is((select count(*) from applications where id = 'e0000000-0000-0000-0000-000000000006'), 0::bigint,
  'P8 an application cannot point at another tenant''s playbook');
select '# P9 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000c',
  $$insert into documents (tenant_id, application_id, doc_type, storage_path)
    values ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000004', 'dui', 'e0000000-0000-0000-0000-000000000001/x/y.pdf')$$);
select is((select count(*) from documents where application_id = 'f0000000-0000-0000-0000-000000000004'), 0::bigint,
  'P9 a document cannot be attached to another tenant''s application');

-- P10/P11 — the case screen's own writes, in the exact shape case-detail.tsx sends.
select '# P10 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000b',
  $$insert into audit_log (actor_id, actor_type, action, entity_type, entity_id, metadata)
    values ('e0000000-0000-0000-0000-00000000000b', 'underwriter', 'case.approved', 'case', 'e0000000-0000-0000-0000-000000000005', '{"application_id": "e0000000-0000-0000-0000-000000000004"}')$$);
select is((select count(*) from audit_log where entity_id = 'e0000000-0000-0000-0000-000000000005' and action = 'case.approved'), 1::bigint,
  'P10 the case screen''s decision audit insert is recorded');
select '# P11 attempt: ' || pg_temp.attempt('e0000000-0000-0000-0000-00000000000b',
  $$insert into case_comments (case_id, author_id, body)
    values ('e0000000-0000-0000-0000-000000000005', 'e0000000-0000-0000-0000-00000000000b', 'nota')$$);
select is((select count(*) from case_comments where case_id = 'e0000000-0000-0000-0000-000000000005'), 1::bigint,
  'P11 the case screen''s comment insert is recorded');

-- P12 — what an anonymous caller (the public anon key) can list.
select is(pg_temp.count_as(null,
  $$select count(*) from products where tenant_id in ('e0000000-0000-0000-0000-000000000001', 'f0000000-0000-0000-0000-000000000001')$$, 'anon'), 0::bigint,
  'P12 an anonymous caller cannot list tenants'' products');

select * from finish();
rollback;
