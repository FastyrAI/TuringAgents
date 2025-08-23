-- Idempotency table: unique dedup keys per org

create table if not exists public.idempotency_keys (
  org_id text not null,
  dedup_key text not null,
  created_at timestamptz default now() not null,
  primary key (org_id, dedup_key)
);


