"""Build the web version of the deck as a single artifact page.

Reads the rendered deck (out/deck.html + kit CSS/JS) and the system outputs
(findings.json, evidence CSVs), and writes out/web/northgate.html:
- the same 15 slides, scaled to the viewer's width, with live liquid glass
- Inter / Inter Tight from Google Fonts (the only font host the viewer allows)
- under each finding slide, a drawer with the method, the document quotes and
  the first evidence rows, each tagged with its source file and line
"""
import csv, html, json, re
from pathlib import Path

DECK = Path("/home/claude/deck/out")
SYS = Path("/home/claude/northgate-recovery/out")
OUT = DECK / "web"; OUT.mkdir(exist_ok=True)
esc = html.escape

page = (DECK / "deck.html").read_text()
glass_css = (DECK / "kit/glass.css").read_text()
deck_css = (DECK / "deck.css").read_text()
glass_js = (DECK / "kit/glass.js").read_text()
findings = {f["id"]: f for f in json.loads((SYS / "findings.json").read_text())["findings"]}
numbers = json.loads((SYS / "deck-numbers.json").read_text())

# the kit's @font-face rules point at local files; the web page carries the same faces inline
import base64
glass_css = re.sub(r'@font-face\s*{[^}]*}\s*', "", glass_css)
FACES = [(400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")]
font_faces = "\n".join(
    '@font-face { font-family: "Instrument Sans"; font-style: normal; font-weight: %d; font-display: block; '
    'src: url(data:font/ttf;base64,%s) format("truetype"); }'
    % (w, base64.b64encode((DECK / "kit/fonts" / f"InstrumentSans-{n}.ttf").read_bytes()).decode())
    for w, n in FACES)

body = page.split("<body>", 1)[1].rsplit("</body>", 1)[0]
body = re.sub(r'<script src="kit/glass.js"></script>', "", body)
slides = re.findall(r'(<section class="slide[\s\S]*?</section>)', body)
assert len(slides) == 15, len(slides)

COLS = {
    "charge_capture": ["source_file", "source_line", "month", "practice_id", "procedures_completed", "procedures_submitted_to_claim", "gap", "excess_value_usd"],
    "denial_priority": ["source_file", "source_line", "month", "practice_id", "payer", "denial_reason", "denied_claims", "written_off_past_filing_limit", "avg_claim_usd"],
    "duplicate_plans": ["source_file", "source_line", "employee_name", "plan_id", "carrier", "sponsoring_entity", "monthly_employer_premium_usd"],
    "ghost_spend": ["source_file", "source_line", "payment_date", "practice_id", "vendor", "category", "amount_usd"],
    "rebates": ["source_file", "source_line", "order_date", "practice_id", "distributor", "amount_usd"],
    "card_processing": ["source_file", "source_line", "month", "practice_id", "processor", "volume_usd", "fees_usd", "effective_rate"],
    "credential_hold": ["source_file", "source_line", "month", "practice_id", "payer", "denied_claims", "denied_amount_usd"],
    "backfill": ["source_file", "source_line", "month", "practice_id", "no_shows", "late_cancellations", "gross_production_usd"],
}
LABEL = {"source_file": "file", "source_line": "line"}


def evidence_rows(fid, n=6):
    path = SYS / "evidence" / f"{fid}.csv"
    if not path.exists():
        return [], []
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    if rows and "part" in rows[0]:
        first = rows[0]["part"]
        rows = [r for r in rows if r["part"] == first]
    cols = [c for c in COLS.get(fid, []) if rows and c in rows[0]]
    return cols, rows[:n]


def fmt(col, v):
    if col == "source_file":
        return v.split("/")[-1]
    try:
        x = float(v)
    except ValueError:
        return v
    if col.endswith("_usd"):
        return f"${x:,.2f}"
    if col.endswith("rate") and x < 1:
        return f"{x * 100:.3f}%"
    return f"{x:,.0f}" if x == int(x) else f"{x:,.3f}"


def drawer(fid, heading):
    f = findings[fid]
    cols, rows = evidence_rows(fid)
    method = "".join(f"<li>{esc(m)}</li>" for m in f["method"])
    docs = "".join(f'<li><span class="q">“{esc(d["quote"])}”</span> <span class="src">{esc(d["path"].split("/")[-1])}</span></li>'
                   for d in f["docs"][:4])
    table = ""
    if rows:
        head = "".join(f"<th>{esc(LABEL.get(c, c.replace('_usd', '').replace('_', ' ')))}</th>" for c in cols)
        trs = "".join("<tr>" + "".join(f'<td class="{"r" if c not in ("source_file","month","practice_id","payer","denial_reason","employee_name","plan_id","carrier","sponsoring_entity","vendor","category","distributor","processor","order_date","payment_date") else ""}">{esc(fmt(c, r[c]))}</td>' for c in cols) + "</tr>" for r in rows)
        table = (f'<p class="lbl">First {len(rows)} of {f["evidence_rows"]:,} evidence rows '
                 f'(full set: <code>python -m northgate explain {fid}</code>)</p>'
                 f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table></div>')
    return (f'<details class="proof"><summary>{esc(heading)}</summary><div class="proof-body">'
            f'<div class="cols"><div><p class="lbl">How the number is built</p><ol>{method}</ol></div>'
            f'<div><p class="lbl">What the documents say</p><ul class="docs">{docs}</ul></div></div>{table}</div></details>')


# which drawer goes under which page: finding pages follow the system's ranks
by_page = {2 + f["rank"]: f["id"] for f in numbers["findings"]}
by_page[9] = "credential_hold"
by_page[14] = "backfill"

frames = []
for i, s in enumerate(slides, start=1):
    extra = drawer(by_page[i], "Show how this number was built") if i in by_page else ""
    frames.append(f'<div class="unit"><div class="frame" id="p{i:02d}">{s}</div>{extra}</div>')

title = "Northgate Recovery Deck"
web_css = """
:root { color-scheme: light; }
html, body { background: var(--field); }
body { margin: 0; padding-inline: 16px; }
.web-top { max-width: 1600px; margin: 0 auto; padding-block: 28px 8px; display: flex; flex-wrap: wrap; gap: 8px 24px;
  align-items: baseline; justify-content: space-between; font: 500 15px/22px var(--font-text); color: var(--ink-2); }
.web-top b { font: 600 17px/22px var(--font-display); color: var(--ink); letter-spacing: -.01em; }
.web-top .keys { color: var(--ink-3); }
.deck-web { max-width: 1600px; margin: 0 auto; display: flex; flex-direction: column; gap: 40px; padding-block: 12px 64px; }
.unit { display: flex; flex-direction: column; gap: 12px; }
.frame { position: relative; width: 100%; aspect-ratio: 16 / 9; overflow: hidden; border-radius: 14px;
  box-shadow: 0 1px 0 rgba(255,255,255,.8) inset, 0 18px 50px -22px rgba(40,70,120,.28), 0 2px 8px -2px rgba(40,70,120,.10); }
.page-pill, .page-pill * { white-space: nowrap; }
.frame > .slide { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
html:not(.web-fit) .frame > .slide { visibility: hidden; }
.proof { border: 1px solid var(--hairline); border-radius: 14px; background: rgba(255,255,255,.55);
  -webkit-backdrop-filter: blur(18px) saturate(1.3); backdrop-filter: blur(18px) saturate(1.3); }
.proof > summary { cursor: pointer; list-style: none; padding: 14px 18px; font: 500 15px/20px var(--font-text); color: var(--ink); }
.proof > summary::-webkit-details-marker { display: none; }
.proof > summary::before { content: "+"; display: inline-block; width: 18px; color: var(--ink-3); font-weight: 600; }
.proof[open] > summary::before { content: "\\2212"; }
.proof > summary:focus-visible { outline: 2px solid #5A86D8; outline-offset: 2px; border-radius: 12px; }
.proof-body { padding: 0 18px 18px; display: flex; flex-direction: column; gap: 16px; font: 400 14px/21px var(--font-text); color: var(--ink); }
.proof .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px 32px; }
.proof .lbl { margin: 0 0 6px; font: 500 12.5px/18px var(--font-text); color: var(--ink-3); letter-spacing: .02em; }
.proof ol, .proof ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; max-width: 68ch; }
.proof ul.docs { list-style: none; padding-left: 0; }
.proof .q { color: var(--ink); }
.proof .src { color: var(--ink-3); font-size: 12.5px; white-space: nowrap; }
.proof code { font: 500 12.5px/18px ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--ink-2); }
.proof .scroll { overflow-x: auto; border-top: 1px solid var(--hairline); }
.proof table { border-collapse: collapse; font: 400 13px/18px var(--font-text); font-variant-numeric: tabular-nums; min-width: 640px; width: 100%; }
.proof th { text-align: left; font-weight: 500; color: var(--ink-3); padding: 8px 10px 6px 0; white-space: nowrap; }
.proof td { padding: 6px 10px 6px 0; border-top: 1px solid var(--hairline); white-space: nowrap; }
.proof td.r, .proof th.r { text-align: right; }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""

fit_js = """
(function () {
  const root = document.documentElement;
  function fit() {
    document.querySelectorAll('.frame').forEach(f => {
      const s = f.querySelector('.slide'); if (!s) return;
      s.style.transform = 'scale(' + (f.clientWidth / 1920) + ')';
    });
    root.classList.add('web-fit');
  }
  const ready = () => { fit(); window.addEventListener('resize', fit); };
  let waited = 0;
  const t = setInterval(() => { waited += 50; if (window.__glassReady || waited > 3000) { clearInterval(t); ready(); } }, 50);
  const frames = () => [...document.querySelectorAll('.frame')];
  document.addEventListener('keydown', e => {
    if (e.target.closest && e.target.closest('summary, input, textarea')) return;
    const fwd = ['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key), back = ['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key);
    if (!fwd && !back) return;
    e.preventDefault();
    const fs = frames(), y = window.scrollY + 2;
    const tops = fs.map(f => f.getBoundingClientRect().top + window.scrollY - 24);
    let i = tops.findIndex(t => t > y);
    if (i === -1) i = fs.length;
    const target = fwd ? tops[Math.min(i, fs.length - 1)] : tops[Math.max((tops.findIndex(t => t >= y - 4) === -1 ? fs.length : tops.findIndex(t => t >= y - 4)) - 1, 0)];
    window.scrollTo({ top: target, behavior: 'smooth' });
  });
})();
"""

n = numbers["totals"]
top = (f'<header class="web-top"><span><b>Northgate: what’s recoverable</b> · Prepared for Dana Reyes, CFO</span>'
       f'<span class="keys">{esc(n["run_rate"]["display"])} a year counted · {esc(n["one_time"]["display"])} one-time · arrow keys move between slides</span></header>')

out = f"""<title>{title}</title>
<style>
{font_faces}
{glass_css}
{deck_css}
{web_css}
</style>
{top}
<main class="deck-web">
{''.join(frames)}
</main>
<script>
{glass_js}
</script>
<script>
{fit_js}
</script>
"""
(OUT / "northgate.html").write_text(out)
print(f"wrote {OUT / 'northgate.html'} ({len(out) / 1024:.0f} KB), drawers on pages {sorted(by_page)}")
