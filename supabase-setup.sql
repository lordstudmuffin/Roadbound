-- Roadbound Quest Log: one-time database setup.
-- Paste this whole file into the Supabase SQL Editor and press Run. It is safe to run again.

-- One row per journal document. "party" is the private journal code the two phones share.
create table if not exists public.docs (
  party      text        not null,
  path       text        not null,
  body       jsonb,
  updated_at timestamptz not null default now(),
  primary key (party, path)
);
create index if not exists docs_party_updated on public.docs (party, updated_at);

-- Every change stamps the row, so the other phone can ask for "everything since my last look".
create or replace function public.touch_docs() returns trigger
language plpgsql as $$
begin
  new.updated_at := clock_timestamp();
  return new;
end $$;

drop trigger if exists docs_touch on public.docs;
create trigger docs_touch before insert or update on public.docs
  for each row execute function public.touch_docs();

-- A phone can only see or change rows whose journal code matches the code it sends with each request.
alter table public.docs enable row level security;

drop policy if exists "journal code required" on public.docs;
create policy "journal code required" on public.docs
  for all to anon
  using (
    length(party) >= 16
    and party = ((current_setting('request.headers', true))::json ->> 'x-party')
  )
  with check (
    length(party) >= 16
    and party = ((current_setting('request.headers', true))::json ->> 'x-party')
  );

grant select, insert, update on public.docs to anon;

-- Merges a small change into a document in one step, so two phones changing
-- different parts of the same quest at the same moment both keep their change.
create or replace function public.jsonb_deep_merge(a jsonb, b jsonb) returns jsonb
language sql immutable as $$
  select case
    when jsonb_typeof(a) = 'object' and jsonb_typeof(b) = 'object' then (
      select coalesce(jsonb_object_agg(
        k,
        case
          when a ? k and b ? k then public.jsonb_deep_merge(a -> k, b -> k)
          when b ? k then b -> k
          else a -> k
        end), '{}'::jsonb)
      from (select jsonb_object_keys(a) as k union select jsonb_object_keys(b)) keys
    )
    else b
  end
$$;

create or replace function public.merge_doc(p_party text, p_path text, p_patch jsonb) returns void
language sql security invoker as $$
  insert into public.docs (party, path, body)
  values (p_party, p_path, p_patch)
  on conflict (party, path) do update
    set body = public.jsonb_deep_merge(coalesce(public.docs.body, '{}'::jsonb), excluded.body)
$$;

grant execute on function public.jsonb_deep_merge(jsonb, jsonb) to anon;
grant execute on function public.merge_doc(text, text, jsonb) to anon;
