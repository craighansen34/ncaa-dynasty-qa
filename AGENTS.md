<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->
- AI calls go through a server route (`src/routes/api/suggest-test.ts` → `src/lib/ai/*.server.ts`) on the Lovable AI Gateway Responses API with streaming; keeps the key server-side and avoids hosting timeouts.
- The QA suite lives in `ncaa-dynasty-qa/` as standalone stdlib Python, independent of the web app; it must run in CI without Node.
- Rule: the QA dashboard (`/dashboard`) reads a bundled snapshot `src/data/qa-snapshot.json` written by `ncaa-dynasty-qa/export_dashboard.py`, and can load CI artifact files in the browser; why: no backend or GitHub access needed.
- Rule: gameplay numbers live only in `ncaa-dynasty-qa/rules.json`; verify.py loads it and `src/lib/dynasty/engine.ts` / the dynasty advisor import it; why: one edit updates the suite and the game.
- Rule: `tests/test_shared_rules.py` (stdlib, CI) checks both sides read rules.json; `web/test_game_parity.py` (Playwright, outside CI) compares behaviour; why: CI must stay stdlib-only.
- Rule: `/dashboard` fetches GitHub Actions runs/artifacts via `src/lib/github.functions.ts` (GitHub connector through the gateway, artifacts unzipped with fflate); why: keeps the GitHub key server-side.
- Rule: the root `.github/workflows/qa.yml` runs the suite with `working-directory: ncaa-dynasty-qa` and must mirror `ncaa-dynasty-qa/.github/workflows/qa.yml`; why: GitHub only runs workflows at the repo root.
- Rule: `/game` staff advisor streams from `src/routes/api/dynasty-advisor.ts` → `src/lib/ai/dynasty-advisor.server.ts` (same gateway pattern as suggest-test), with rules taken from rules.json; why: advice cannot contradict the game rules.
- Rule: `web/test_game_parity.py` writes `src/data/game-parity.json` locally and runs in the root `qa.yml` `game-parity` job (matrix, uploads `game-parity-py<ver>`), which `/dashboard` auto-loads from the remembered repo's latest run; why: parity results without a terminal, suite job stays stdlib-only.
- Rule (see rules_config rule for persistence): `/rules` edits `ncaa-dynasty-qa/rules.json` via `src/lib/rules.functions.ts` (fs write, zod-validated); why: one editor for game and suite; works only where the project files are writable (preview/dev). The editor is `src/components/RulesEditorPanel.tsx`, also embedded live (auto-save) on `/game`; after a save it calls `engine.applyRules` (in-place swap + `RULES_EVENT`), and the advisor re-reads rules.json per request; why: edits apply instantly without reloads. Rule descriptions live in rules.json `_descriptions` (ignored by the engines); the editor's live preview (`RulesPreview.tsx`) recomputes prestige/hours/roster from the unsaved draft.
- Rule: saved rules live in the Lovable Cloud table `rules_config` (single row id=1); `saveRules` requires sign-in + the `admin` role (first account to call `claim_rules_owner` becomes owner), also writes rules.json when writable (preview); `__root` loads the row via `src/lib/rules-online.ts` → `applyRules`, and the advisor server overlays it; why: the published site can't write files, so edits must persist online. The QA suite/CI still read rules.json only.
- Rule: real dynasty seasons are stored per user in the Cloud table `dynasty_seasons` (RLS own rows), read by `SaveSeasonsPreview.tsx` on the Prestige formula panel; why: the formula replays real results across visits and devices.
