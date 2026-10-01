create type public.app_role as enum ('admin', 'user');

create table public.user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  role public.app_role not null,
  unique (user_id, role)
);
grant select on public.user_roles to authenticated;
grant all on public.user_roles to service_role;
alter table public.user_roles enable row level security;
create policy "Users see own roles" on public.user_roles for select to authenticated using (auth.uid() = user_id);

create or replace function public.has_role(_user_id uuid, _role public.app_role)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from public.user_roles where user_id = _user_id and role = _role) $$;

-- The first signed-in person to claim becomes the only rules owner.
create or replace function public.claim_rules_owner()
returns boolean language plpgsql security definer set search_path = public
as $$
begin
  if auth.uid() is null then return false; end if;
  if not exists (select 1 from public.user_roles where role = 'admin') then
    insert into public.user_roles (user_id, role) values (auth.uid(), 'admin');
  end if;
  return public.has_role(auth.uid(), 'admin');
end $$;
revoke execute on function public.claim_rules_owner() from anon, public;
grant execute on function public.claim_rules_owner() to authenticated;

create table public.rules_config (
  id int primary key default 1 check (id = 1),
  data jsonb not null,
  updated_at timestamptz not null default now(),
  updated_by uuid
);
grant select on public.rules_config to anon, authenticated;
grant insert, update on public.rules_config to authenticated;
grant all on public.rules_config to service_role;
alter table public.rules_config enable row level security;
create policy "Anyone can read rules" on public.rules_config for select to anon, authenticated using (true);
create policy "Owner can add rules" on public.rules_config for insert to authenticated with check (public.has_role(auth.uid(), 'admin'));
create policy "Owner can change rules" on public.rules_config for update to authenticated using (public.has_role(auth.uid(), 'admin')) with check (public.has_role(auth.uid(), 'admin'));