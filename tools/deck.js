// Buy or Wait? — product deck (HackerRank Orchestrate, Sep 2026)
const pptxgen = require("pptxgenjs");
const curve = require("/tmp/deck_curve.json");

const BG = "F7F8FA", DARK = "0F1B2D", PRIMARY = "0F766E", ACCENT = "D97706";
const TEXT = "1E293B", MUTED = "64748B", TINT = "E6F2F0", AMBERTINT = "FDF3E3";
const W = 13.33, H = 7.5, M = 0.5;
const MONO = "Courier New", SANS = "Arial";

let p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Varun";
p.title = "Buy or Wait? — financial affordability agent";

const hair = (s, x, y, w) => s.addShape(p.shapes.LINE, { x, y, w, h: 0, line: { color: "D8DEE6", width: 0.75 } });
const bu = () => ({ code: "25B8", indent: 12 });

// ---------- 1 · Cover (dark) ----------
let s = p.addSlide();
s.background = { color: DARK };
s.addText("Buy or Wait?", { x: M, y: 1.5, w: 12.3, h: 1.3, fontSize: 66, bold: true, color: "FFFFFF", fontFace: SANS, margin: 0 });
s.addText([
  { text: "A deterministic financial-affordability agent. ", options: { color: "CBD5E1" } },
  { text: "The LLM describes evidence; pure code decides.", options: { color: ACCENT, bold: true } },
], { x: M, y: 2.85, w: 12.3, h: 0.6, fontSize: 22, fontFace: SANS, margin: 0 });
s.addText("HackerRank Orchestrate · September 2026", { x: M, y: 3.5, w: 12.3, h: 0.4, fontSize: 15, color: "94A3B8", fontFace: SANS, margin: 0 });
const stats = [["250", "requests scored"], ["90-day", "balance safety forecast"], ["0", "invalid output rows"], ["$0.0007", "total LLM cost"]];
stats.forEach(([n, l], i) => {
  const x = M + i * 3.13;
  s.addText(n, { x, y: 4.7, w: 2.9, h: 0.9, fontSize: 40, bold: true, color: i === 3 ? ACCENT : "5EEAD4", fontFace: SANS, margin: 0 });
  s.addText(l, { x, y: 5.6, w: 2.9, h: 0.4, fontSize: 13, color: "94A3B8", fontFace: SANS, margin: 0 });
});
s.addText("One row per request: the safest way to pay — full, partial, installments, wait, or not at all.", { x: M, y: 6.6, w: 12.3, h: 0.4, fontSize: 14, color: "CBD5E1", fontFace: SANS, margin: 0 });

// ---------- 2 · The decision ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("Every request becomes one structured decision", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
s.addText('"Can I afford this laptop?" — the agent answers with facts, dates and amounts, not adjectives.', { x: M, y: 1.15, w: 12.3, h: 0.4, fontSize: 15, color: MUTED, fontFace: SANS, margin: 0 });
const fields = [
  ["amount_safe_to_pay", "max amount safe to pay today, before optional spending changes"],
  ["affordability_status", "affordable_now · with_plan · later · not_affordable"],
  ["recommended_payment_method", "the safest eligible way to proceed"],
  ["payment_plan", "chronological dates + amounts, exact to the payment option"],
  ["earliest_date_for_full_payment", "first day the full amount passes the safety check"],
  ["spending_changes_needed", "flexible recurring expenses to stop or reduce (≤ 3)"],
  ["decision_explanation", "grounded facts behind the recommendation"],
];
fields.forEach(([f, d], i) => {
  const y = 1.75 + i * 0.62;
  hair(s, M, y - 0.08, 12.3);
  s.addText(f, { x: M, y, w: 4.6, h: 0.5, fontSize: 15, bold: true, color: PRIMARY, fontFace: MONO, margin: 0, valign: "middle" });
  s.addText(d, { x: 5.3, y, w: 7.5, h: 0.5, fontSize: 14, color: TEXT, fontFace: SANS, margin: 0, valign: "middle" });
});
hair(s, M, 1.75 + 7 * 0.62 - 0.08, 12.3);

// ---------- 3 · Architecture ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("Architecture: the LLM describes, deterministic code decides", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
const boxes = [
  ["dataset/", "9 CSVs · 16 images\n215 messages", "F1F5F9", TEXT],
  ["state.py", "recurring bills\nforex · conflicts\n90-day simulator", TINT, TEXT],
  ["evidence.py", "messages + images\n→ amendment JSON", AMBERTINT, TEXT],
  ["decider.py", "candidates · safety\n6-key ranking", TINT, TEXT],
  ["validator.py", "schema · options\nflexible-only changes", TINT, TEXT],
  ["output.csv", "250 rows\nexact schema", DARK, "FFFFFF"],
];
boxes.forEach(([t, d, fill, tc], i) => {
  const x = M + i * 2.11, w = 1.95;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 2.1, w, h: 1.75, fill: { color: fill }, rectRadius: 0.07, shadow: { type: "outer", color: "000000", blur: 5, offset: 2, angle: 45, opacity: 0.12 } });
  s.addText(t, { x: x + 0.12, y: 2.25, w: w - 0.24, h: 0.4, fontSize: 15, bold: true, color: tc === "FFFFFF" ? "5EEAD4" : PRIMARY, fontFace: MONO, margin: 0 });
  s.addText(d, { x: x + 0.12, y: 2.7, w: w - 0.24, h: 1.0, fontSize: 11.5, color: tc, fontFace: SANS, margin: 0 });
  if (i < boxes.length - 1) s.addText("→", { x: x + w - 0.06, y: 2.7, w: 0.3, h: 0.5, fontSize: 20, bold: true, color: MUTED, fontFace: SANS, margin: 0, align: "center" });
});
s.addText([
  { text: "amber lane — untrusted inputs, structured only. ", options: { color: ACCENT, bold: true } },
  { text: "Everything downstream of evidence is pure, offline-replayable code: cached observations let the decider re-run with zero API calls.", options: { color: TEXT } },
], { x: M, y: 4.35, w: 12.3, h: 0.7, fontSize: 15, fontFace: SANS, margin: 0 });
const nums = [["27", "logged design decisions"], ["19", "unit + integration tests"], ["0.3s", "for all 250 requests"], ["stdlib", "only — zero dependencies"]];
nums.forEach(([n, l], i) => {
  const x = M + i * 3.13;
  s.addText(n, { x, y: 5.3, w: 2.9, h: 0.8, fontSize: 36, bold: true, color: PRIMARY, fontFace: SANS, margin: 0 });
  s.addText(l, { x, y: 6.1, w: 2.9, h: 0.4, fontSize: 13, color: MUTED, fontFace: SANS, margin: 0 });
});

// ---------- 4 · The 90-day safety check (real curve) ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("The 90-day safety check, on real data", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
s.addText("user_06 · EUR 620.40 investment · balance EUR 1,662.90 · floor EUR 800. Stopping the EUR 19 streaming subscription lifts the whole curve — the same full payment that is unsafe today becomes safe.", { x: M, y: 1.12, w: 12.3, h: 0.65, fontSize: 14, color: MUTED, fontFace: SANS, margin: 0 });
const days = Array.from({ length: 60 }, (_, i) => (i % 10 === 0 ? `day ${i}` : ""));
s.addChart(p.charts.LINE, [
  { name: "without spending changes", labels: days, values: curve.no_change.slice(0, 60) },
  { name: "streaming stopped", labels: days, values: curve.with_change.slice(0, 60) },
  { name: "minimum balance floor", labels: days, values: curve.minimum.slice(0, 60) },
], {
  x: M, y: 1.9, w: 12.3, h: 4.3, chartColors: ["94A3B8", PRIMARY, ACCENT],
  lineSize: 2.5, lineDataSymbol: "none", lineSmooth: false,
  chartArea: { fill: { color: "FFFFFF" } },
  catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
  valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
  showLegend: true, legendPos: "t", legendColor: TEXT, legendFontSize: 12,
  valAxisTitle: "balance (EUR)", showValAxisTitle: true, valAxisTitleColor: MUTED, valAxisTitleFontSize: 12,
});
s.addText("Source: code/state.py simulator, real dataset/user_06 · max safe today before changes: EUR 518.81 of 620.40", { x: M, y: 6.55, w: 12.3, h: 0.4, fontSize: 12, color: MUTED, fontFace: SANS, margin: 0 });

// ---------- 5 · The interface ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("The interface: six commands, no dependencies", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
s.addText("Python 3 standard library only. Evidence results are disk-cached, so every command is deterministic and replayable offline.", { x: M, y: 1.12, w: 12.3, h: 0.4, fontSize: 14, color: MUTED, fontFace: SANS, margin: 0 });
const cmds = [
  ["python3 code/main.py", "score all 250 requests → output.csv (0.3s)"],
  ["python3 code/main.py --samples", "the 25 solved examples → calibration run"],
  ["python3 code/main.py --offline", "re-decide from cached evidence, zero API calls"],
  ["python3 code/evaluation/score.py \\\n  --pred … --gold …", "per-field accuracy vs solved samples"],
  ["python3 code/evaluation/analyze.py …", "failure clusters: field, type, status, worst rows"],
  ["python3 -m unittest discover -s tests", "19 unit + integration tests"],
];
cmds.forEach(([c, d], i) => {
  const y = 1.75 + i * 0.82;
  hair(s, M, y - 0.1, 12.3);
  s.addText(c, { x: M, y, w: 6.6, h: 0.7, fontSize: 13.5, bold: true, color: PRIMARY, fontFace: MONO, margin: 0, valign: "middle" });
  s.addText(d, { x: 7.4, y, w: 5.4, h: 0.7, fontSize: 13.5, color: TEXT, fontFace: SANS, margin: 0, valign: "middle" });
});
hair(s, M, 1.75 + 6 * 0.82 - 0.1, 12.3);

// ---------- 6 · What the agent says ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("What the agent says — real output rows", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
const ex = [
  ["affordable_now · full_payment", PRIMARY, TINT,
   "Pay INR 122,500 today. This leaves at least INR 122,400 available over the next 90 days.",
   "2023-08-12:122500"],
  ["affordable_with_plan · installments", PRIMARY, TINT,
   "Use 3 installments of INR 95,194.67, starting 2026-03-01. This leaves at least INR 166,100 available.",
   "2026-03-01:95194.67|2026-03-31:95194.67|2026-04-30:95194.67"],
  ["not_affordable · not_recommended", ACCENT, AMBERTINT,
   "Do not make this payment by 2025-02-10. None of the available options keeps the INR 225,400 minimum protected.",
   "none"],
];
ex.forEach(([tag, tagc, fill, text, plan], i) => {
  const y = 1.35 + i * 1.85;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: M, y, w: 12.3, h: 1.62, fill: { color: fill }, rectRadius: 0.07 });
  s.addText(tag, { x: 0.85, y: y + 0.14, w: 11.6, h: 0.34, fontSize: 13, bold: true, color: tagc, fontFace: MONO, margin: 0 });
  s.addText(`"${text}"`, { x: 0.85, y: y + 0.5, w: 11.6, h: 0.55, fontSize: 16, italic: true, color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(`payment_plan:  ${plan}`, { x: 0.85, y: y + 1.1, w: 11.6, h: 0.34, fontSize: 12.5, color: MUTED, fontFace: MONO, margin: 0 });
});

// ---------- 7 · Scorecard ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("Scorecard against the 25 solved examples", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
s.addChart(p.charts.BAR, [{
  name: "field accuracy",
  labels: ["amount_safe_to_pay", "affordability_status", "recommended_method", "payment_plan", "earliest_full_date", "spending_changes", "decision_explanation"],
  values: [16, 68, 68, 68, 64, 88, 100],
}], {
  x: M, y: 1.5, w: 8.3, h: 5.0, barDir: "bar", varyColors: true,
  chartColors: [ACCENT, PRIMARY, PRIMARY, PRIMARY, PRIMARY, PRIMARY, "0B3B36"],
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT, dataLabelFontSize: 12, dataLabelFormatCode: "0\\%",
  chartArea: { fill: { color: "FFFFFF" } }, catAxisLabelColor: TEXT, catAxisLabelFontSize: 12,
  valAxisLabelColor: MUTED, valAxisMaxVal: 100, valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
  showLegend: false,
});
s.addText("67.4%", { x: 9.2, y: 1.7, w: 3.6, h: 1.1, fontSize: 60, bold: true, color: PRIMARY, fontFace: SANS, margin: 0 });
s.addText("of all 7 fields correct\n(118 / 175 field checks)", { x: 9.2, y: 2.85, w: 3.6, h: 0.7, fontSize: 14, color: TEXT, fontFace: SANS, margin: 0 });
s.addText([
  { text: "Every output row passes the adversarial validator — bounds, option-exact installment schedules, flexible-only changes.", options: { bullet: bu(), breakLine: true } },
  { text: "Explations are template-grounded: 100% name the protected minimum.", options: { bullet: bu(), breakLine: true } },
  { text: "The open gap is forecast precision on amount_safe_to_pay — the tooling (calibrator + residual diagnostic) targets exactly that.", options: { bullet: bu() } },
], { x: 9.2, y: 3.7, w: 3.7, h: 2.8, fontSize: 12.5, color: TEXT, fontFace: SANS, paraSpaceAfter: 8, margin: 0 });
s.addText("Source: code/evaluation/score.py vs dataset/sample_requests.csv, offline reproducible run", { x: M, y: 6.75, w: 12.3, h: 0.35, fontSize: 12, color: MUTED, fontFace: SANS, margin: 0 });

// ---------- 8 · Design decisions ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("Four decisions that make it defensible", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
const dec = [
  ["1", "LLM describes, code decides", "The model only structures messages and images into amendment JSON. Amounts, dates, plans and rankings are computed — auditable and exact."],
  ["2", "CONTRACT.md is law", "One human-readable + machine-mirrored contract gates every module and every agent. Parallel work without merge hell."],
  ["3", "An adversarial validator gates output", "Bounds, enums, option-exact schedules, flexible-only changes. Any rejected row is replaced by a conservative fallback — an invalid row can never ship."],
  ["4", "Evidence is cached, decisions replay", "Every LLM result is content-hash cached to disk. The decider re-runs offline with zero API calls — temp 0 alone is not reproducibility."],
];
dec.forEach(([n, t, d], i) => {
  const y = 1.5 + i * 1.32;
  hair(s, M, y - 0.12, 12.3);
  s.addText(n, { x: M, y: y + 0.05, w: 0.8, h: 1.0, fontSize: 44, bold: true, color: ACCENT, fontFace: SANS, margin: 0 });
  s.addText(t, { x: 1.55, y, w: 4.1, h: 1.1, fontSize: 17, bold: true, color: PRIMARY, fontFace: SANS, margin: 0, valign: "middle" });
  s.addText(d, { x: 5.9, y, w: 6.9, h: 1.1, fontSize: 13.5, color: TEXT, fontFace: SANS, margin: 0, valign: "middle" });
});
hair(s, M, 1.5 + 4 * 1.32 - 0.12, 12.3);

// ---------- 9 · Ops ----------
s = p.addSlide(); s.background = { color: BG };
s.addText("Engineering under free-tier reality", { x: M, y: M, w: 12.3, h: 0.6, fontSize: 30, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
s.addText("The evidence pass ran on congested free LLM endpoints (OpenRouter). The architecture absorbs it.", { x: M, y: 1.12, w: 12.3, h: 0.4, fontSize: 14, color: MUTED, fontFace: SANS, margin: 0 });
const ops = [
  ["40", "LLM calls for all evidence", "batched 16 messages per call"],
  ["373K", "tokens total (56K in / 317K out)", "reasoning-model overhead measured, then switched"],
  ["$0.0007", "estimated total cost", "free-tier models; cost table per model in the report"],
  ["6", "model failover ladder", "429 backoff + Retry-After; per-item cache keys include the provider"],
];
ops.forEach(([n, t, d], i) => {
  const x = M + (i % 2) * 6.35, y = 1.85 + Math.floor(i / 2) * 1.85;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w: 6.0, h: 1.6, fill: { color: "FFFFFF" }, rectRadius: 0.07, shadow: { type: "outer", color: "000000", blur: 5, offset: 2, angle: 45, opacity: 0.1 } });
  s.addText(n, { x: x + 0.3, y: y + 0.18, w: 2.2, h: 1.2, fontSize: 40, bold: true, color: PRIMARY, fontFace: SANS, margin: 0, valign: "middle" });
  s.addText(t, { x: x + 2.6, y: y + 0.22, w: 3.2, h: 0.65, fontSize: 13.5, bold: true, color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(d, { x: x + 2.6, y: y + 0.92, w: 3.2, h: 0.55, fontSize: 11.5, color: MUTED, fontFace: SANS, margin: 0 });
});
s.addText("Cache keys = content hash + provider, so mock results can never masquerade as real extractions — a bug we caught and fixed during the build.", { x: M, y: 5.85, w: 12.3, h: 0.5, fontSize: 14, color: TEXT, fontFace: SANS, margin: 0 });
s.addText("Source: code/evaluation/usage_log.jsonl → evaluation/usage_report.md", { x: M, y: 6.6, w: 12.3, h: 0.35, fontSize: 12, color: MUTED, fontFace: SANS, margin: 0 });

// ---------- 10 · Closing (dark) ----------
s = p.addSlide(); s.background = { color: DARK };
s.addText("Run it yourself", { x: M, y: 0.7, w: 12.3, h: 0.9, fontSize: 44, bold: true, color: "FFFFFF", fontFace: SANS, margin: 0 });
const steps = [
  ["1", "python3 code/main.py", "score all 250 requests → output.csv"],
  ["2", "python3 code/main.py --samples", "25 solved examples, calibration view"],
  ["3", "python3 code/evaluation/score.py --pred cache/output_samples.csv --gold dataset/sample_requests.csv", "field-level scorecard"],
  ["4", "python3 -m unittest discover -s tests", "19 tests, all green"],
];
steps.forEach(([n, c, d], i) => {
  const y = 1.8 + i * 1.02;
  s.addText(n, { x: M, y, w: 0.5, h: 0.8, fontSize: 26, bold: true, color: ACCENT, fontFace: SANS, margin: 0 });
  s.addText(c, { x: 1.15, y, w: 7.4, h: 0.8, fontSize: 13, bold: true, color: "5EEAD4", fontFace: MONO, margin: 0, valign: "middle" });
  s.addText(d, { x: 8.7, y, w: 4.1, h: 0.8, fontSize: 12.5, color: "CBD5E1", fontFace: SANS, margin: 0, valign: "middle" });
});
s.addText("Submission: code.zip · output.csv · log.txt (chat transcript)", { x: M, y: 6.1, w: 12.3, h: 0.4, fontSize: 15, color: "CBD5E1", fontFace: SANS, margin: 0 });
s.addText("decisions.md — 27 logged decisions, ready for the AI-judge interview", { x: M, y: 6.55, w: 12.3, h: 0.4, fontSize: 13, color: "94A3B8", fontFace: SANS, margin: 0 });

p.writeFile({ fileName: "/Users/varun/Downloads/Varun/Orchestrate/BuyOrWait_Product_Deck.pptx" }).then(() => console.log("deck written"));
