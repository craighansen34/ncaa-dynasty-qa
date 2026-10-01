import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Sign in — NCAA Dynasty Rules" },
      { name: "description", content: "Sign in to change the dynasty rules shared by the game and the test suite." },
      { property: "og:title", content: "Sign in — NCAA Dynasty Rules" },
      { property: "og:description", content: "Rules owner sign-in for NCAA Dynasty." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function done() {
    await supabase.rpc("claim_rules_owner");
    void nav({ to: "/rules" });
  }

  // Returning from Google: finish sign-in.
  useEffect(() => { void supabase.auth.getSession().then(({ data }) => { if (data.session) void done(); }); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    if (mode === "in") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setMsg(error.message); else await done();
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/rules` } });
      if (error) setMsg(error.message);
      else if (data.session) await done();
      else setMsg("Check your email to confirm your account, then sign in.");
    }
    setBusy(false);
  }

  async function google() {
    const r = await lovable.auth.signInWithOAuth("google", { redirect_uri: `${window.location.origin}/auth` });
    if (r.error) { setMsg("Google sign-in didn't work. Try again."); return; }
    if (r.redirected) return;
    await done();
  }

  const input = "w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">NCAA Dynasty · Rules</p>
      <h1 className="mb-2 text-2xl font-bold">{mode === "in" ? "Sign in" : "Create account"}</h1>
      <p className="mb-6 text-sm text-muted-foreground">Only the rules owner can change the rules. The first account to sign in becomes the owner.</p>
      <button onClick={() => void google()} className="mb-4 w-full rounded-md border border-border px-3 py-2 text-sm">Continue with Google</button>
      <form onSubmit={submit} className="space-y-3">
        <input className={input} type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className={input} type="password" required minLength={6} placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button disabled={busy} className="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">{mode === "in" ? "Sign in" : "Create account"}</button>
      </form>
      {msg && <p className="mt-3 text-sm text-destructive">{msg}</p>}
      <p className="mt-4 text-sm">
        <button className="text-primary underline" onClick={() => setMode(mode === "in" ? "up" : "in")}>{mode === "in" ? "Create an account" : "I already have an account"}</button>
        {" · "}<Link to="/rules" className="text-primary underline">Back to rules</Link>
      </p>
    </main>
  );
}
