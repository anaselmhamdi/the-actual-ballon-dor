export type Pos = "GK" | "DEF" | "MID" | "FWD";

export interface Cand {
  id: string; pos: Pos;
  o: number | null; oa: number | null; b: number | null; ba: number | null; t: number | null;
  euro: boolean | null; eclub: boolean | null; club: string | null;
  m: number; min: number; g: number; pg: number; a: number; xg: number | null; xa: number | null;
  bm: number; tr: string[]; lm: boolean;
}

export interface Year {
  year: number; from: string; to: string; tier: "A" | "B" | "C";
  rule: "europeans" | "european_clubs" | "open"; awarded: boolean;
  real: { id: string | null; name: string; rank: number; points: number | null }[];
  c: Cand[];
}

export interface BiasRow { key: string; label: string; coef: number; lo: number; hi: number }

export interface Data {
  generated: string;
  players: Record<string, { n: string; s: string; p: Pos; nat: string | null }>;
  years: Year[];
  bias: { unit: string; n: number; r2: number; rows: BiasRow[] };
}

export interface Settings { output: number; big: number; trophy: number; fairness: number; historical: boolean }

export const DEFAULTS: Settings = { output: 50, big: 25, trophy: 25, fairness: 70, historical: true };

export function parts(c: Cand, s: Settings) {
  const sum = s.output + s.big + s.trophy || 1;
  const f = s.fairness / 100;
  const blend = (pos: number | null, all: number | null) => f * (pos ?? -1) + (1 - f) * (all ?? -1);
  return {
    output: (s.output / sum) * blend(c.o, c.oa),
    big: (s.big / sum) * blend(c.b, c.ba),
    trophy: (s.trophy / sum) * (c.t ?? -1),
  };
}

export function score(c: Cand, s: Settings): number {
  const p = parts(c, s);
  return p.output + p.big + p.trophy;
}

export function eligible(c: Cand, y: Year, historical: boolean): boolean {
  if (!historical || y.rule === "open") return true;
  if (y.rule === "european_clubs") return c.eclub !== false;
  return c.euro !== false && c.eclub !== false;
}

export function ranked(y: Year, s: Settings, historical = s.historical) {
  return y.c
    .filter((c) => eligible(c, y, historical))
    .map((c) => ({ c, score: score(c, s) }))
    .sort((a, b) => b.score - a.score);
}

export interface Verdict {
  year: Year;
  model: { c: Cand; score: number } | undefined;
  runnerUp: { c: Cand; score: number } | undefined;
  realId: string | null;
  realName: string | null;
  realScore: number | null;
  realModelRank: number | null;
  changed: boolean;
  gap: number | null;
  ruleDecided: boolean;
}

export function verdicts(data: Data, s: Settings): Verdict[] {
  return data.years.map((y) => {
    const r = ranked(y, s);
    const open = s.historical ? ranked(y, s, false) : r;
    const real = y.real.find((x) => x.rank === 1);
    const realIdx = real?.id ? r.findIndex((x) => x.c.id === real.id) : -1;
    const realScore = realIdx >= 0 ? r[realIdx].score : null;
    const model = r[0];
    return {
      year: y,
      model,
      runnerUp: r[1],
      realId: real?.id ?? null,
      realName: real?.name ?? null,
      realScore,
      realModelRank: realIdx >= 0 ? realIdx + 1 : null,
      changed: !!real && !!model && model.c.id !== real.id,
      gap: model && realScore !== null ? model.score - realScore : null,
      ruleDecided: s.historical && !!open[0] && !!model && open[0].c.id !== model.c.id,
    };
  });
}

export function cabinet(data: Data, vs: Verdict[]) {
  const tally = new Map<string, { model: number; real: number; years: number[] }>();
  const get = (id: string) => tally.get(id) ?? tally.set(id, { model: 0, real: 0, years: [] }).get(id)!;
  for (const v of vs) {
    if (v.model) { const t = get(v.model.c.id); t.model += 1; t.years.push(v.year.year); }
    if (v.realId && v.year.awarded) get(v.realId).real += 1;
  }
  return [...tally.entries()]
    .map(([id, t]) => ({ id, name: data.players[id]?.n ?? id, ...t }))
    .sort((a, b) => b.model - a.model || b.real - a.real);
}
