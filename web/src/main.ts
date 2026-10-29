import { DEFAULTS, verdicts, type Data, type Settings } from "./model";
import {
  biasChart, cabinetChart, consoleGaps, decadeOf, decades, explorerMeta, explorerModel, explorerReal, ledgerPanel,
  robbedList, robberyRows, ruleYears,
} from "./render";

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector<T>(sel)!;
const form = $<HTMLFormElement>("#console");

function readUrl(): { s: Settings; year: number | null; decade: number | null } {
  const q = new URLSearchParams(location.search);
  const w = (q.get("w") ?? "").split(",").map(Number);
  const s = { ...DEFAULTS };
  if (w.length === 3 && w.every((n) => n >= 0 && n <= 100)) [s.output, s.big, s.trophy] = w;
  const f = Number(q.get("f"));
  if (q.has("f") && f >= 0 && f <= 100) s.fairness = f;
  if (q.get("r") === "open") s.historical = false;
  return { s, year: Number(q.get("y")) || null, decade: Number(q.get("d")) || null };
}

const state = readUrl();

function writeUrl() {
  const q = new URLSearchParams();
  const s = state.s;
  if (s.output !== DEFAULTS.output || s.big !== DEFAULTS.big || s.trophy !== DEFAULTS.trophy) q.set("w", `${s.output},${s.big},${s.trophy}`);
  if (s.fairness !== DEFAULTS.fairness) q.set("f", String(s.fairness));
  if (!s.historical) q.set("r", "open");
  if (state.year) q.set("y", String(state.year));
  if (state.decade) q.set("d", String(state.decade));
  const qs = q.toString();
  history.replaceState(null, "", qs ? `?${qs}${location.hash}` : location.pathname + location.hash);
}

function syncForm() {
  for (const k of ["output", "big", "trophy", "fairness"] as const) {
    (form.elements.namedItem(k) as HTMLInputElement).value = String(state.s[k]);
    $(`[data-for="${k}"]`).textContent = k === "fairness" ? `${state.s[k]}%` : String(state.s[k]);
  }
  ($(state.s.historical ? "#rules-hist" : "#rules-open") as HTMLInputElement).checked = true;
}

function selectDecade(data: Data, decade: number, focus = false) {
  state.decade = decade;
  for (const d of decades(data)) {
    const tab = $(`#tab-${d}`);
    const on = d === decade;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    $(`#dec-${d}`).hidden = !on;
    if (on && focus) tab.focus();
  }
}

function render(data: Data) {
  const s = state.s;
  const vs = verdicts(data, s);
  const awarded = vs.filter((v) => v.year.awarded);
  $("#changed").textContent = String(awarded.filter((v) => v.changed).length);
  $("#awarded").textContent = String(awarded.length);
  $("#console-gaps").innerHTML = consoleGaps(data, vs);

  const ds = decades(data);
  const current = state.decade && ds.includes(state.decade) ? state.decade : 2010;
  $("#ledger-panels").innerHTML = ds.map((d) => ledgerPanel(data, vs, d, d !== current)).join("");
  selectDecade(data, current);

  $("#rob-table tbody").innerHTML = robberyRows(data, vs);
  $("#robbed").innerHTML = robbedList(data, vs);
  const ruleH = $("#rule-h");
  ruleH.hidden = !s.historical;
  $("#rule-years").hidden = !s.historical;
  $("#rule-years").textContent = ruleYears(vs);

  renderYear(data);
  $("#cabinet-chart").innerHTML = cabinetChart(data, vs);
}

function renderYear(data: Data) {
  const year = data.years.find((y) => y.year === state.year) ?? data.years.find((y) => y.year === 2012)!;
  $("#exp-year").textContent = String(year.year);
  $("#exp-meta").textContent = explorerMeta(year);
  $("#exp-model tbody").innerHTML = explorerModel(data, year, state.s);
  $("#exp-real tbody").innerHTML = explorerReal(data, year, state.s);
  $<HTMLSelectElement>("#year-select").value = String(year.year);
  const idx = data.years.indexOf(year);
  $<HTMLButtonElement>("#prev-year").disabled = idx === 0;
  $<HTMLButtonElement>("#next-year").disabled = idx === data.years.length - 1;
}

async function main() {
  const data: Data = await (await fetch("/data.json")).json();
  $("#generated").textContent = data.generated;

  const ds = decades(data);
  $("#decade-tabs").innerHTML = ds
    .map((d) => `<button role="tab" type="button" id="tab-${d}" aria-controls="dec-${d}" aria-selected="false" tabindex="-1">${d}s</button>`)
    .join("");
  $("#decade-tabs").addEventListener("click", (e) => {
    const t = (e.target as HTMLElement).closest("button");
    if (t) { selectDecade(data, Number(t.id.slice(4))); writeUrl(); }
  });
  $("#decade-tabs").addEventListener("keydown", (e) => {
    const i = ds.indexOf(state.decade ?? 2010);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : -1;
    if (next >= 0 && next < ds.length) { e.preventDefault(); selectDecade(data, ds[next], true); writeUrl(); }
  });

  $<HTMLSelectElement>("#year-select").innerHTML = data.years.map((y) => `<option value="${y.year}">${y.year}</option>`).join("");
  $<HTMLSelectElement>("#year-select").addEventListener("change", (e) => {
    state.year = Number((e.target as HTMLSelectElement).value); renderYear(data); writeUrl();
  });
  const step = (d: number) => {
    const ys = data.years.map((y) => y.year);
    const i = ys.indexOf(state.year ?? 2012) + d;
    if (i >= 0 && i < ys.length) { state.year = ys[i]; renderYear(data); writeUrl(); }
  };
  $("#prev-year").addEventListener("click", () => step(-1));
  $("#next-year").addEventListener("click", () => step(1));

  document.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest<HTMLAnchorElement>("a[data-year]");
    if (a) { state.year = Number(a.dataset.year); renderYear(data); writeUrl(); }
  });

  form.addEventListener("input", () => {
    const fd = new FormData(form);
    for (const k of ["output", "big", "trophy", "fairness"] as const) state.s[k] = Number(fd.get(k));
    state.s.historical = fd.get("rules") === "historical";
    syncForm(); render(data); writeUrl();
  });
  form.addEventListener("submit", (e) => e.preventDefault());

  $("#share").addEventListener("click", async () => {
    writeUrl();
    try {
      await navigator.clipboard.writeText(location.href);
      $("#share-status").textContent = "Link copied, with these weights and this year.";
    } catch {
      $("#share-status").textContent = `Copy this link: ${location.href}`;
    }
  });

  $("#bias-chart").innerHTML = biasChart(data);
  const prev = data.bias.rows.find((r) => r.key === "prev_winner");
  if (prev) $("#bias-note").textContent = `Having won the year before is worth ${prev.coef.toFixed(1)} points of vote share on its own.`;

  if (state.year && !state.decade) state.decade = decadeOf(state.year);
  syncForm();
  render(data);
}

main();
