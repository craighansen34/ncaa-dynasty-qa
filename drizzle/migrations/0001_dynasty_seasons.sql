CREATE TABLE public.dynasty_seasons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL DEFAULT auth.uid(),
  dynasty text NOT NULL DEFAULT 'My dynasty',
  season integer NOT NULL,
  wins integer NOT NULL,
  losses integer NOT NULL DEFAULT 0,
  roster_size integer,
  prestige_before numeric,
  prestige_after numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, dynasty, season)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.dynasty_seasons TO authenticated;
GRANT ALL ON public.dynasty_seasons TO service_role;
ALTER TABLE public.dynasty_seasons ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Own seasons read" ON public.dynasty_seasons FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Own seasons add" ON public.dynasty_seasons FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Own seasons change" ON public.dynasty_seasons FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Own seasons remove" ON public.dynasty_seasons FOR DELETE TO authenticated USING (auth.uid() = user_id);