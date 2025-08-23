create table if not exists public.poison_counters (
  org_id text not null,
  dedup_key text not null,
  count integer not null default 0,
  updated_at timestamptz default now(),
  primary key (org_id, dedup_key)
);


