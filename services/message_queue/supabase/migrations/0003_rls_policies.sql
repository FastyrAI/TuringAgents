-- Basic RLS scaffolding (adjust per environment needs). This assumes server-side
-- components use service role key; RLS policies are placeholders for future UI/API.

alter table if exists public.messages enable row level security;
alter table if exists public.message_events enable row level security;
alter table if exists public.dlq_messages enable row level security;
alter table if exists public.idempotency_keys enable row level security;

-- Example: allow service role to bypass RLS (default behavior in Supabase with service key)
-- Add per-user/org policies later as needed.


