import { cabinet, parts, ranked, type Data, type Settings, type Verdict, type Year } from "./model";

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const fmt = (n: number | null | undefined, d = 2) => (n === null || n === undefined ? "" : n.toFixed(d));

export const name = (data: Data, id: string | null | undefined, fallback = "") =>
  esc((id && data.players[id]?.n) || fallback);

const TIER_NOTE: Record<Year["tier"], string> = {
  A: "Match logs plus expected goals",
  B: "Match logs, goals and assists",
  C: "Thinner match logs",
};

export const decadeOf = (y: number) => Math.floor(y / 10) * 10;

export function ledgerRows(data: Data, vs: Verdict[], decade: number): string {
  return vs
    .filter((v) => decadeOf(v.year.year) === decade)
    .map((v) => {
      const y = v.year;
      const real = y.awarded ? name(data, v.realId, v.realName ?? "") : "Not awarded";
      const model = v.model ? name(data, v.model.c.id) : "";
      const flags = [
        y.tier === "C" ? `<span class="tag">thin data</span>` : "",
        v.ruleDecided ? `<span class="tag">rule decided</span>` : "",
      ].join("");
      return `<tr class="${v.changed ? "is-changed" : ""}">
        <th scope="row" class="num"><a href="#explorer" data-year="${y.year}">${y.year}</a></th>
        <td>${real}</td>
        <td class="ledger__model">${model}${flags}</td>
        <td class="num">${v.realModelRank ?? (y.awarded ? "unrated" : "")}</td>
        <td class="num">${v.changed && v.gap !== null ? "+" + fmt(v.gap) : ""}</td>
      </tr>`;
    })
    .join("");
}

export function ledgerPanel(data: Data, vs: Verdict[], decade: number, hidden: boolean): string {
  return `<section role="tabpanel" id="dec-${decade}" aria-labelledby="tab-${decade}" ${hidden ? "hidden" : ""}>
    <table class="table ledger">
      <caption class="visually-hidden">${decade}s</caption>
      <thead><tr><th scope="col" class="num">Year</th><th scope="col">Won it</th><th scope="col">Model’s pick</th><th scope="col" class="num">Winner’s model rank</th><th scope="col" class="num">Margin</th></tr></thead>
      <tbody>${ledgerRows(data, vs, decade)}</tbody>
    </table></section>`;
}

export function decades(data: Data): number[] {
  return [...new Set(data.years.map((y) => decadeOf(y.year)))];
}

export function robberyRows(data: Data, vs: Verdict[]): string {
  return vs
    .filter((v) => v.changed && v.gap !== null && v.year.awarded)
    .sort((a, b) => b.gap! - a.gap!)
    .slice(0, 8)
    .map((v) => `<tr>
      <th scope="row" class="num"><a href="#explorer" data-year="${v.year.year}">${v.year.year}</a></th>
      <td>${name(data, v.realId, v.realName ?? "")}</td>
      <td>${name(data, v.model!.c.id)}</td>
      <td class="num">${v.realModelRank}</td>
      <td class="num">+${fmt(v.gap)}</td></tr>`)
    .join("");
}

export function robbedList(data: Data, vs: Verdict[]): string {
  const counts = new Map<string, number[]>();
  for (const v of vs) {
    if (v.changed && v.year.awarded && v.model) counts.set(v.model.c.id, [...(counts.get(v.model.c.id) ?? []), v.year.year]);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[1][0] - b[1][0])
    .slice(0, 6)
    .map(([id, years]) => `<li><span class="robbed__name">${name(data, id)}</span><span class="num robbed__years">${years.join(", ")}</span></li>`)
    .join("");
}

export function ruleYears(vs: Verdict[]): string {
  const ys = vs.filter((v) => v.ruleDecided).map((v) => v.year.year);
  return ys.length ? ys.join(", ") : "None under these weights.";
}

export function explorerModel(data: Data, y: Year, s: Settings): string {
  const r = ranked(y, s).slice(0, 10);
  const max = Math.max(...r.map((x) => {
    const p = parts(x.c, s);
    return Math.max(0, p.output) + Math.max(0, p.big) + Math.max(0, p.trophy) + Math.max(0, p.consistency);
  }), 0.01);
  return r.map((x, i) => {
    const p = parts(x.c, s);
    const w = (v: number) => ((Math.max(0, v) / max) * 100).toFixed(1);
    const xgxa = x.c.xg !== null ? fmt((x.c.xg ?? 0) + (x.c.xa ?? 0), 1) : "";
    const sub = [x.c.pos, x.c.club].filter(Boolean).map((t) => esc(t!)).join(", ");
    return `<tr${i === 0 ? ' class="is-lead"' : ""}>
      <td class="num">${i + 1}</td>
      <td><span class="p-name">${name(data, x.c.id)}</span><span class="p-sub">${sub}${x.c.lm ? ", league games estimated" : ""}</span></td>
      <td><span class="bars" title="Output ${fmt(p.output)}, big games ${fmt(p.big)}, trophies ${fmt(p.trophy)}, consistency ${fmt(p.consistency)}${x.c.tr.length ? ": " + esc(x.c.tr.join(", ")) : ""}">
        <span class="bar bar--o" style="--w:${w(p.output)}%"></span><span class="bar bar--b" style="--w:${w(p.big)}%"></span><span class="bar bar--t" style="--w:${w(p.trophy)}%"></span><span class="bar bar--k" style="--w:${w(p.consistency)}%"></span>
      </span><span class="num bars__total">${fmt(x.score)}</span></td>
      <td class="num">${x.c.g}</td><td class="num">${x.c.a}</td><td class="num">${xgxa}</td><td class="num">${x.c.kr ?? ""}${x.c.kr !== null ? "%" : ""}</td></tr>`;
  }).join("");
}

export function explorerReal(data: Data, y: Year, s: Settings): string {
  if (!y.awarded) return `<tr><td colspan="3">France Football cancelled the 2020 award.</td></tr>`;
  const order = ranked(y, s).map((x) => x.c.id);
  return y.real.slice(0, 10).map((r) => {
    const mr = r.id ? order.indexOf(r.id) : -1;
    return `<tr><td class="num">${r.rank}</td><td>${name(data, r.id, r.name)}</td><td class="num">${mr >= 0 ? mr + 1 : "unrated"}</td></tr>`;
  }).join("");
}

export function explorerMeta(y: Year): string {
  const rule = { europeans: "Europeans only", european_clubs: "European clubs only", open: "Open to all" }[y.rule];
  return `Window ${y.from} to ${y.to}. ${TIER_NOTE[y.tier]}. ${rule} at the time.`;
}

export function cabinetChart(data: Data, vs: Verdict[]): string {
  const rows = cabinet(data, vs).filter((r) => r.model > 0 || r.real > 1).slice(0, 14);
  const max = Math.max(...rows.map((r) => Math.max(r.model, r.real)), 1);
  return `<ol class="cab">${rows.map((r) => `<li>
      <span class="cab__name">${esc(r.name)}</span>
      <span class="cab__bars">
        <span class="cab__bar cab__bar--real" style="--w:${(r.real / max) * 100}%"><span class="num">${r.real}</span></span>
        <span class="cab__bar cab__bar--model" style="--w:${(r.model / max) * 100}%"><span class="num">${r.model}</span></span>
      </span></li>`).join("")}</ol>`;
}

export function biasChart(data: Data): string {
  const rows = data.bias.rows;
  const lo = Math.min(0, ...rows.map((r) => r.lo));
  const hi = Math.max(...rows.map((r) => r.hi));
  const x = (v: number) => (((v - lo) / (hi - lo)) * 100).toFixed(2);
  return `<ol class="coef" style="--zero:${x(0)}%">${rows.map((r) => `<li>
      <span class="coef__label">${esc(r.label)}</span>
      <span class="coef__track"><span class="coef__ci" style="--a:${x(r.lo)}%;--b:${x(r.hi)}%"></span><span class="coef__dot" style="--x:${x(r.coef)}%"></span></span>
      <span class="num coef__val">${r.coef > 0 ? "+" : ""}${r.coef.toFixed(1)}</span></li>`).join("")}</ol>
    <p class="coef__axis">Vote-share points, 95% intervals, ${data.bias.n.toLocaleString("en")} player-seasons.</p>`;
}

export function consoleGaps(data: Data, vs: Verdict[]): string {
  return vs
    .filter((v) => v.changed && v.gap !== null && v.year.awarded)
    .sort((a, b) => b.gap! - a.gap!)
    .slice(0, 3)
    .map((v) => `<li><span class="num">${v.year.year}</span><s>${name(data, v.realId, v.realName ?? "")}</s><b>${name(data, v.model!.c.id)}</b></li>`)
    .join("");
}
