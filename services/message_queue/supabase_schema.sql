-- Message audit schema for Supabase

create table if not exists public.messages (
  id bigserial primary key,
  message_id text unique not null,
  org_id text not null,
  agent_id text,
  type text not null,
  priority int not null,
  status text default 'QUEUED',
  payload jsonb not null,
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null
);

create index if not exists idx_messages_org_created on public.messages (org_id, created_at desc);

create table if not exists public.message_events (
  id bigserial primary key,
  message_id text not null,
  org_id text not null,
  event_type text not null, -- created|enqueued|dequeued|processing|completed|failed|retry_scheduled|dead_letter
  details jsonb,
  created_at timestamptz default now() not null
);

create index if not exists idx_message_events_msg on public.message_events (message_id, created_at asc);
create index if not exists idx_message_events_org on public.message_events (org_id, created_at desc);

create table if not exists public.dlq_messages (
  id bigserial primary key,
  org_id text not null,
  original_message jsonb not null,
  error jsonb not null,
  can_replay boolean default true,
  dlq_timestamp timestamptz default now() not null
);

create index if not exists idx_dlq_org_time on public.dlq_messages (org_id, dlq_timestamp desc);

-- Note: enable RLS/policies as needed; server components should use service role key.


