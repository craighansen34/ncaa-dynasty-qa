import R from "../../ncaa-dynasty-qa/rules.json";

export type TimelineRow = {
  season: number;
  roster: number | null;
  after: number | null;
  source: string;
};

const W = 720;
const H = 220;
const PAD = { l: 44, r: 44, t: 16, b: 28 };
const INNER_W = W - PAD.l - PAD.r;
const INNER_H = H - PAD.t - PAD.b;

function hoursFor(prestige: number | null): number | null {
  if (prestige == null) return null;
  return (R.WEEKLY_HOURS as Record<string, number>)[String(prestige)] ?? null;
}

export function PrestigeTimeline({ rows }: { rows: TimelineRow[] }) {
  const pts = [...rows]
    .filter((r) => r.after != null)
    .sort((a, b) => a.season - b.season);
  if (pts.length === 0) return null;

  const seasons = pts.map((p) => p.season);
  const minS = Math.min(...seasons);
  const maxS = Math.max(...seasons);
  const span = Math.max(1, maxS - minS);
  const x = (s: number) => PAD.l + ((s - minS) / span) * INNER_W;

  const maxHours = Math.max(...(Object.values(R.WEEKLY_HOURS) as number[]));
  const yPrestige = (p: number) =>
    PAD.t + INNER_H - ((p - R.MIN_PRESTIGE) / (R.MAX_PRESTIGE - R.MIN_PRESTIGE)) * INNER_H;
  const yHours = (h: number) => PAD.t + INNER_H - (h / maxHours) * INNER_H;
  const yRoster = (n: number) => PAD.t + INNER_H - (n / R.MAX_ROSTER) * INNER_H;

  const line = (vals: (number | null)[], yFn: (v: number) => number) => {
    let prev: number | null = null;
    return vals
      .map((v, i) => {
        const cmd = prev == null ? "M" : "L";
        prev = v;
        return v == null ? null : `${cmd}${x(pts[i]!.season).toFixed(1)},${yFn(v).toFixed(1)}`;
      })
      .filter(Boolean)
      .join(" ");
  };

  const prestigePath = line(pts.map((p) => p.after), yPrestige);
  const hoursPath = line(pts.map((p) => hoursFor(p.after)), yHours);
  const rosterPath = line(pts.map((p) => p.roster), yRoster);

  const rosterLimitY = yRoster(R.MAX_ROSTER);
  const maxPrestigeY = yPrestige(R.MAX_PRESTIGE);
  const minPrestigeY = yPrestige(R.MIN_PRESTIGE);

  return (
    <div className="mb-6 rounded-md border border-border p-3" data-testid="saves-timeline">
      <h2 className="mb-1 text-sm font-semibold">Prestige timeline</h2>
      <p className="mb-2 text-xs text-muted-foreground">
        How prestige, weekly hours and roster size move season to season. Dashed lines mark the rules thresholds: roster limit {R.MAX_ROSTER}, prestige {R.MIN_PRESTIGE}★–{R.MAX_PRESTIGE}★.
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Prestige, hours and roster by season">
        {/* threshold lines */}
        <line x1={PAD.l} x2={W - PAD.r} y1={rosterLimitY} y2={rosterLimitY} stroke="currentColor" strokeDasharray="4 3" className="text-destructive" strokeWidth="1" />
        <line x1={PAD.l} x2={W - PAD.r} y1={maxPrestigeY} y2={maxPrestigeY} stroke="currentColor" strokeDasharray="4 3" className="text-muted-foreground" strokeWidth="1" />
        <line x1={PAD.l} x2={W - PAD.r} y1={minPrestigeY} y2={minPrestigeY} stroke="currentColor" strokeDasharray="4 3" className="text-muted-foreground" strokeWidth="1" />
        <text x={W - PAD.r + 4} y={rosterLimitY + 3} className="fill-destructive" fontSize="9">{R.MAX_ROSTER}</text>
        <text x={W - PAD.r + 4} y={maxPrestigeY + 3} className="fill-muted-foreground" fontSize="9">{R.MAX_PRESTIGE}★</text>
        <text x={W - PAD.r + 4} y={minPrestigeY + 3} className="fill-muted-foreground" fontSize="9">{R.MIN_PRESTIGE}★</text>

        {/* series */}
        <path d={prestigePath} fill="none" strokeWidth="2" className="stroke-primary" />
        <path d={hoursPath} fill="none" strokeWidth="2" className="stroke-amber-500" />
        <path d={rosterPath} fill="none" strokeWidth="2" className="stroke-emerald-600" />

        {/* points + season labels */}
        {pts.map((p) => (
          <g key={`${p.source}-${p.season}`}>
            {p.after != null && <circle cx={x(p.season)} cy={yPrestige(p.after)} r="3" className="fill-primary" />}
            {hoursFor(p.after) != null && <circle cx={x(p.season)} cy={yHours(hoursFor(p.after)!)} r="3" className="fill-amber-500" />}
            {p.roster != null && <circle cx={x(p.season)} cy={yRoster(p.roster)} r="3" className="fill-emerald-600" />}
            <text x={x(p.season)} y={H - 8} textAnchor="middle" className="fill-muted-foreground" fontSize="10">
              S{p.season}
            </text>
          </g>
        ))}
      </svg>
      <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-primary" /> Prestige (★)</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-amber-500" /> Hours/week</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-emerald-600" /> Roster</span>
      </div>
    </div>
  );
}
