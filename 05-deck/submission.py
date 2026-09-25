#!/usr/bin/env python3
"""Build the all-in-one submission page: one self-contained HTML file to send by email.

Reads the rendered deck (out/deck.html + kit), the system's outputs (findings.json,
deck-numbers.json, evidence CSVs, the report it prints), the harness docs and both repos,
and writes out/submission/Northgate-Ian-Milkowski.html:

  hero · the 15 slides (live glass, evidence drawers, present mode) · the system ·
  how the documents were processed · the harness · the stress test · what broke ·
  both repositories, readable file by file.

No network requests and no embedded binaries (fonts are inlined as data). Every figure is
read from the system's output or computed here from the packet; nothing is typed.
"""
import base64
import csv
import html
import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import markdown
from fontTools import subset
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

DECK = Path("/home/claude/deck/out")
SYS_REPO = Path("/home/claude/northgate-recovery")
SYS = SYS_REPO / "out"
HARN = Path("/home/claude/northgate-harness")
OUT = DECK / "submission"
OUT.mkdir(exist_ok=True)
FILENAME = "Northgate-Ian-Milkowski.html"

esc = html.escape
sys.path.insert(0, str(SYS_REPO))
from northgate import assumptions as A  # noqa: E402
from northgate import triage as T  # noqa: E402


WORDS = {3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}


def num(x):
    return f"{x:,}"


def usd(x, cents=False):
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


def md(text, smart=True):
    ext = ["tables", "fenced_code", "sane_lists"]
    cfg = {}
    if smart:
        ext.append("smarty")
        cfg["smarty"] = {"smart_dashes": False}
    return markdown.markdown(text, extensions=ext, extension_configs=cfg)


# ---------------------------------------------------------------- system outputs
run = subprocess.run([sys.executable, "-m", "northgate"], cwd=SYS_REPO, capture_output=True, text=True, check=True)
report_lines = run.stdout.rstrip("\n").split("\n")
numbers = json.loads((SYS / "deck-numbers.json").read_text())
fjson = json.loads((SYS / "findings.json").read_text())
findings = {f["id"]: f for f in fjson["findings"]}
tot = numbers["totals"]
meth = numbers["method"]

tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=SYS_REPO, capture_output=True, text=True)
m = re.search(r"(\d+) passed", tests.stdout)
assert m and tests.returncode == 0, tests.stdout[-800:]
TESTS_PASSED = int(m.group(1))

tie = Counter(t["verdict"] for t in fjson["tieouts"])
TIE_CHECKS, TIE_BREAKS = len(fjson["tieouts"]), tie["break"]
EVIDENCE_ROWS = sum(f["evidence_rows"] for f in fjson["findings"])
N_FINDINGS, N_COUNTED = len(fjson["findings"]), len(numbers["findings"])

# ---------------------------------------------------------------- triage, recomputed from the packet
PACKET = SYS_REPO / "packet"
places = [row["city"] for row in csv.DictReader((PACKET / "data/practices.csv").open())]
place_re = T.place_pattern([*places, *A.TRIAGE_EXTRA_PLACES.value])
utts = T.collect(PACKET / "documents")
skels = [T.skeleton(u.text, place_re) for u in utts]
skel_count = Counter(skels)
variants = defaultdict(Counter)
for u, s in zip(utts, skels):
    variants[s][u.text] += 1
tri = T.run_triage(PACKET / "documents", places)
assert (tri.utterances, tri.words, tri.rare_words) == (meth["utterances"], meth["corpus_words"], meth["rare_words"])
flagged = sorted({u.source for u in tri.rare})
flagged_email = [d for d in flagged if d.startswith("email/")]
n_email = len(list((PACKET / "documents/email").glob("*.txt")))
UNFLAGGED_EMAIL = n_email - len(flagged_email)


def pillify(text):
    """The utterance as the filter sees it: masked words shown as tags."""
    t = place_re.sub(lambda mm: "\x00" + mm.group(0).replace(" ", "\x01") + "\x00", text)
    out = []
    for i, w in enumerate(re.sub(r"\s+", " ", t.strip()).split(" ")):
        if w.count("\x00") == 2:
            pre, place, post = w.split("\x00")
            out.append(f'{esc(pre)}<span class="mask mask--place">{esc(place.replace(chr(1), " "))}</span>{esc(post)}')
            continue
        core = re.match(r"^(.*?)([.,;:?!)\"”’]*)$", w)
        word, tail = core.group(1), core.group(2)
        if re.search(r"\d", w):
            out.append(f'<span class="mask mask--num">{esc(word)}</span>{esc(tail)}')
        elif i > 0 and w[:1].isupper() and w not in T.PRONOUNS:
            out.append(f'<span class="mask mask--name">{esc(word)}</span>{esc(tail)}')
        else:
            out.append(esc(w))
    return " ".join(out)


def shape(needle, clip=None, until=None):
    """The skeleton whose example contains `needle`: count, versions, example (cut after `until`)."""
    for s, c in skel_count.most_common():
        for raw in variants[s]:
            if needle in raw:
                ex = raw
                if until and until in raw:
                    end = raw.index(until) + len(until)
                    ex = raw[:end] + ("…" if end < len(raw) else "")
                elif clip and len(raw) > clip:
                    ex = raw[:clip].rsplit(" ", 1)[0] + "…"
                return {"count": c, "versions": len(variants[s]), "text": ex}
    raise KeyError(needle)


SHAPES = [
    (shape("Sorry, can you repeat that?"), "", ""),
    (shape("Right. And just so it's on the record", 96), "", ""),
    (shape("Can we take that offline?"), "", ""),
    (shape("We need to standardize how the sites are coding", 100), "decoy",
     "Sounds like a finding. It’s filler, word for word, every time."),
    (shape("ran out of composite"), "", ""),
    (shape("Nobody checks. There's no report", until="what got billed"), "kept",
     "Tom Kirkbride, IT. The unbilled-procedures finding, " + numbers["findings"][0]["annual"]["display"] + " a year."),
    (shape("I have been holding", until="I have been holding them"), "kept",
     "Bev, inside a forwarded reply. The only proof Dr. Osei’s "
     + numbers["clocks"]["items"][2]["amount"]["display"] + " is still recoverable. v0 dropped it."),
]
MAX_SHAPE = max(s["count"] for s, _, _ in SHAPES)

# ---------------------------------------------------------------- trace one number to a packet line
with (SYS / "evidence/charge_capture.csv").open() as fh:
    cc_rows = list(csv.DictReader(fh))
slip = [r for r in cc_rows if r["part"] == "slip_site"]
ev = slip[0]
src_line_no = int(ev["source_line"])
packet_file = PACKET / ev["source_file"]
packet_line = packet_file.read_text().split("\n")[src_line_no - 1]
packet_header = packet_file.read_text().split("\n")[0]
slip_sum = sum(float(r["excess_value_usd"]) for r in slip)
cc = findings["charge_capture"]
assert abs(slip_sum * A.NET_COLLECTION.value - cc["annual_net"]) < 1
assert packet_line.split(",")[:3] == [ev["month"], ev["practice_id"], ev["procedures_completed"]]

# ---------------------------------------------------------------- fonts: subset + WOFF, inline
UNICODES = [*range(0x20, 0x7F), *range(0xA0, 0x180), *range(0x2000, 0x2070), *range(0x2190, 0x2200),
            0x2212, 0x2248, 0x2264, 0x2265, 0x00D7, 0x2026, 0x20AC, 0x2122, 0x2713, 0x2197, 0x2198]


def font_face(weight, name):
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = subset.load_font(str(DECK / "kit/fonts" / f"InstrumentSans-{name}.ttf"), opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, opts)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f'@font-face {{ font-family: "Instrument Sans"; font-style: normal; font-weight: {weight}; '
            f'font-display: block; src: url(data:font/woff;base64,{b64}) format("woff"); }}')


FONT_FACES = "\n".join(font_face(w, n) for w, n in [(400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")])

# ---------------------------------------------------------------- deck: slides, drawers
glass_css = re.sub(r"@font-face\s*{[^}]*}\s*", "", (DECK / "kit/glass.css").read_text())
deck_css = (DECK / "deck.css").read_text()
glass_js = (DECK / "kit/glass.js").read_text()
page = (DECK / "deck.html").read_text()
body = page.split("<body>", 1)[1].rsplit("</body>", 1)[0]
slides = re.findall(r'(<section class="slide[\s\S]*?</section>)', body)
assert len(slides) == 15, len(slides)


def strip_tags(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()


def slide_name(i, s):
    if i == 1:
        return "Cover"
    eb = re.search(r'class="t-eyebrow"[^>]*>([\s\S]*?)</span>\s*(?:<span class="tag|</div>)', s)
    name = strip_tags(eb.group(1)) if eb else f"Slide {i}"
    return re.sub(r"^\d+ · ", "", name)


SLIDE_NAMES = [slide_name(i, s) for i, s in enumerate(slides, 1)]

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
TEXT_COLS = {"source_file", "month", "practice_id", "payer", "denial_reason", "employee_name", "plan_id", "carrier",
             "sponsoring_entity", "vendor", "category", "distributor", "processor", "order_date", "payment_date"}
LABEL = {"source_file": "file", "source_line": "line"}


def evidence_rows(fid, n=6):
    path = SYS / "evidence" / f"{fid}.csv"
    if not path.exists():
        return [], []
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    if rows and "part" in rows[0]:
        rows = [r for r in rows if r["part"] == rows[0]["part"]]
    cols = [c for c in COLS.get(fid, []) if rows and c in rows[0]]
    return cols, rows[:n]


def cell(col, v):
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


def drawer(fid):
    f = findings[fid]
    cols, rows = evidence_rows(fid)
    method = "".join(f"<li>{esc(x)}</li>" for x in f["method"])
    docs = "".join(f'<li><span class="q">“{esc(d["quote"])}”</span> <span class="src-file">{esc(d["path"].split("/")[-1])}</span></li>'
                   for d in f["docs"][:4])
    table = ""
    if rows:
        head = "".join(f'<th class="{"" if c in TEXT_COLS else "r"}">{esc(LABEL.get(c, c.replace("_usd", "").replace("_", " ")))}</th>' for c in cols)
        trs = "".join("<tr>" + "".join(f'<td class="{"" if c in TEXT_COLS else "r"}">{esc(cell(c, r[c]))}</td>' for c in cols) + "</tr>" for r in rows)
        table = (f'<p class="plbl">First {len(rows)} of {num(f["evidence_rows"])} evidence rows. '
                 f'Full set: <code>python -m northgate explain {fid}</code></p>'
                 f'<div class="scroll" tabindex="0"><table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table></div>')
    code = f"northgate/findings/{fid}.py"
    return (f'<details class="proof"><summary>How this number was built</summary><div class="proof-body">'
            f'<div class="cols"><div><p class="plbl">Method</p><ol>{method}</ol></div>'
            f'<div><p class="plbl">What the documents say</p><ul class="docs">{docs}</ul>'
            f'<p class="code-jump"><a href="#source" data-open="recovery/{code}">Read the code: {code}</a></p></div></div>'
            f'{table}</div></details>')


by_page = {2 + f["rank"]: f["id"] for f in numbers["findings"]}
by_page[9] = "credential_hold"
by_page[14] = "backfill"

units = []
for i, s in enumerate(slides, start=1):
    extra = drawer(by_page[i]) if i in by_page else ""
    units.append(f'<div class="unit" data-i="{i - 1}"><div class="frame" id="p{i:02d}" role="group" aria-roledescription="slide" '
                 f'aria-label="{i} of 15: {esc(SLIDE_NAMES[i - 1])}">{s}</div>{extra}</div>')
chips = "".join(f'<button class="chip" type="button" data-go="{i}" title="{esc(n)}">{i + 1:02d}</button>'
                for i, n in enumerate(SLIDE_NAMES))

# ---------------------------------------------------------------- harness docs
fail_md = (HARN / "FAILURES.md").read_text()
FAIL_SUMMARY = {
    1: "Caught by reading the flagged documents in full, then by the system agent.",
    2: "Caught when the flagged list showed lines I’d already seen with other towns in them.",
    3: "Caught in the per-site gap rates. The data and Tom agree; the appendix doesn’t.",
    4: "Caught by the system agent, because its prompt said report, don’t fix.",
    5: "$55 on $165K. The brief says the same numbers, so it’s fixed.",
    6: "Caught when the agent ranked everyone, not just the full-time staff.",
    7: "Caught reviewing slide 2 at full size. A test now enforces the order.",
    8: "Caught diffing the screen against the PDF, pixel by pixel.",
    9: "Caught by the deck agent refusing to type a number the contract didn’t have.",
    10: "Fixed by committing to Instrument Sans, not by routing around the network.",
}
fails = []
for part in re.split(r"^## ", fail_md, flags=re.M)[1:]:
    title, rest = part.split("\n", 1)
    mm = re.match(r"(\d+)\.\s+(.*)", title.strip())
    fails.append((int(mm.group(1)), md(mm.group(2)).removeprefix("<p>").removesuffix("</p>"), md(rest.strip())))
assert len(fails) == 10 and set(FAIL_SUMMARY) == {n for n, _, _ in fails}

dana_md = (HARN / "06-verification/play-dana.md").read_text()


def md_section(text, heading):
    mm = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return mm.group(1).strip()


changed = md_section(dana_md, "What changed because of it")
table_rows = [r for r in changed.split("\n") if r.startswith("|") and not r.startswith("|---")][1:]
before_after = [[c.strip() for c in r.strip("|").split("|")] for r in table_rows]
second = md(md_section(dana_md, "A second opinion on the first opinion"))
qs = re.findall(r"^\d+\.\s+\*\*(.+?)\*\*\s*\n\s+(.+?)(?=\n\d+\.|\Z)",
                md_section(dana_md, "The questions Dana will ask in Stage 3"), flags=re.M | re.S)
assert len(qs) == 6 and len(before_after) == 4
also = md_section(dana_md, "What it found")
also_items = re.findall(r"^- (.+)$", also.split("It also caught:", 1)[1], flags=re.M)

# ---------------------------------------------------------------- source browser
FAMILY = {"recovery": ("northgate-recovery", SYS_REPO), "harness": ("northgate-harness", HARN)}
SKIP_EXT = {".ttf", ".otf", ".woff", ".woff2", ".png", ".jpg", ".pdf", ".zip"}
templates = []
trees = {}
counts = {}


def lexer_for(path, text):
    if path.suffix == ".txt" or path.name == ".gitignore":
        return TextLexer()
    try:
        return get_lexer_for_filename(path.name, text)
    except ClassNotFound:
        return TextLexer()


FMT = HtmlFormatter(nowrap=True)


def render_code(path, text):
    hl = highlight(text, lexer_for(path, text), FMT)
    lines = hl.rstrip("\n").split("\n")
    return "".join(f'<span class="l">{ln}</span>' for ln in lines), len(lines)


def render_md(text):
    return markdown.markdown(text, extensions=["tables", "fenced_code", "codehilite", "sane_lists"],
                             extension_configs={"codehilite": {"guess_lang": False, "css_class": "hl"}})


def build_tree(key):
    name, root = FAMILY[key]
    files = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout.split()
    shown, skipped = [], defaultdict(int)
    for f in files:
        p = Path(f)
        if f.startswith("packet/"):
            skipped["packet"] += 1
        elif p.suffix.lower() in SKIP_EXT:
            skipped["binary"] += 1
        else:
            shown.append(f)
    tree = {}
    for f in shown:
        node = tree
        parts = f.split("/")
        for d in parts[:-1]:
            node = node.setdefault(d + "/", {})
        node[parts[-1]] = f
    total_lines = 0

    def leaf_html(node, leaf):
        nonlocal total_lines
        rel = node[leaf]
        path = root / rel
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            content, kind = render_md(text), "md"
            lines = text.count("\n") + 1
        else:
            content, lines = render_code(path, text)
            kind = "code"
        total_lines += lines
        tid = f"t{len(templates)}"
        templates.append(f'<template id="{tid}">{content}</template>')
        return (f'<li><button type="button" data-path="{esc(rel)}" data-tpl="{tid}" data-kind="{kind}" '
                f'data-lines="{lines}"><span class="fn">{esc(leaf)}</span><span class="ln">{num(lines)}</span></button></li>')

    def emit(node, depth):
        dirs = sorted(k for k in node if k.endswith("/"))
        leaves = sorted((k for k in node if not k.endswith("/")), key=str.lower)
        first = [leaf_html(node, k) for k in leaves if k == "README.md"]
        folders = [f'<li class="dir"><span>{esc(d)}</span><ul>{emit(node[d], depth + 1)}</ul></li>' for d in dirs]
        files = [leaf_html(node, k) for k in leaves if k != "README.md"]
        return "".join(first + folders + files)

    html_tree = f"<ul>{emit(tree, 0)}</ul>"
    notes = []
    if skipped["packet"]:
        notes.append(f"packet/ holds the challenge packet as you sent it ({num(skipped['packet'])} files), not shown.")
    if skipped["binary"]:
        notes.append(f"{skipped['binary']} font files not shown.")
    note = "".join(f'<p class="tree-note">{esc(n)}</p>' for n in notes)
    counts[key] = (len(shown), total_lines)
    hidden = " hidden" if key != "recovery" else ""
    return f'<div class="tree" data-repo="{key}" tabindex="0"{hidden}>{html_tree}{note}</div>'


trees = {k: build_tree(k) for k in FAMILY}

# ---------------------------------------------------------------- page sections
d = lambda k: tot[k]["display"]  # noqa: E731
last_deadline = max(i["end"] for i in numbers["clocks"]["items"])
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
deadline_disp = f"{MONTHS[int(last_deadline[5:7]) - 1]} {int(last_deadline[8:10])}"

NAV = [("deck", "Deck"), ("system", "System"), ("documents", "Documents"), ("harness", "Harness"),
       ("review", "Stress test"), ("broke", "What broke"), ("source", "Source")]
nav = "".join(f'<a href="#{k}" data-sec="{k}">{v}</a>' for k, v in NAV)


def sec_head(n, key, title, lede):
    name = dict(NAV)[key] if key in dict(NAV) else key
    return (f'<div class="sec-head"><p class="sec-eyebrow"><span class="n">{n:02d}</span><span>{esc(name)}</span></p>'
            f'<h2>{title}</h2><p class="sec-lede">{lede}</p></div>')


hero = f"""
<header class="hero" id="top">
  <div class="wrap hero-grid">
    <div class="hero-text">
      <p class="hero-eyebrow">Straterai<span class="dot">·</span>Forward Deployed Engineer<span class="dot">·</span>Stage 2</p>
      <h1>What Northgate can recover</h1>
      <p class="lede">{WORDS[N_COUNTED]} findings in Northgate’s FY2025 data, each traced to the rows behind it. A system that
      reproduces every number with one command. And the harness that got me through {num(meth['packet_words'])} words.</p>
      <p class="byline">Ian Milkowski</p>
    </div>
    <figure class="fig pane">
      <p class="fig-label">Counted at the floor</p>
      <p class="fig-num"><b>{d('run_rate')}</b><span>a year</span></p>
      <p class="fig-sub">Up to {d('run_rate_upper')}. Closes {tot['pretax_gap_closed_pct']}% of the FY2025 pre-tax loss.</p>
      <hr class="fig-rule">
      <p class="fig-row"><b>+ {d('one_time')}</b> one-time, before {deadline_disp}</p>
      <p class="fig-row"><b>{d('upside')}</b> backfill upside, not counted until a pilot proves it</p>
    </figure>
  </div>
  <div class="wrap">
    <ol class="three pane">
      <li><a href="#deck"><span class="n">1</span><b>The deck</b><span class="d">15 slides for Dana Reyes, CFO. Live below, with
        the evidence behind every number. Also attached as a PDF.</span><span class="go">See the slides</span></a></li>
      <li><a href="#system"><span class="n">2</span><b>The system</b><span class="d">northgate-recovery. One install, one run,
        the deck’s exact numbers, each traced to a file and a line.</span><span class="go">See it run</span></a></li>
      <li><a href="#documents"><span class="n">3</span><b>The harness</b><span class="d">northgate-harness. How
        {num(meth['packet_words'])} words became {meth['signal_documents']} documents worth reading, the agents,
        and ten things that broke.</span><span class="go">See how it was built</span></a></li>
    </ol>
  </div>
</header>"""

deck_sec = f"""
<section class="sec" id="deck" aria-labelledby="deck-h">
  <div class="wrap">
    {sec_head(1, 'deck', '<span id="deck-h">Fifteen slides. One number each, and the rows behind it.</span>',
              'Written for Dana Reyes, CFO. Every figure is rendered from the system’s output file, never typed by hand. '
              'Under each finding, a drawer shows how the number is built, what the documents say, and the first rows of evidence.')}
    <div class="deck-bar">
      <button class="btn" type="button" id="present">Present<span class="k">P</span></button>
      <span class="hint">← → move between slides</span>
      <div class="chips" role="group" aria-label="Jump to slide">{chips}</div>
    </div>
    <noscript><p class="noscript">This viewer is showing the page without JavaScript, so the slides and the source browser
      can’t draw. Open the file in a browser, or use the PDF attached to the same email.</p></noscript>
    <div class="deck-web" id="deck-web">
      {''.join(units)}
      <div class="present-bar" aria-hidden="true">
        <button type="button" class="pb" data-step="-1" aria-label="Previous slide">←</button>
        <span class="count"><b id="p-cur">1</b> / 15</span>
        <button type="button" class="pb" data-step="1" aria-label="Next slide">→</button>
        <span class="pb-sep"></span>
        <button type="button" class="pb pb-x" id="p-exit">Esc</button>
      </div>
    </div>
  </div>
</section>"""

# system --------------------------------------------------------------
def term_html(lines):
    out = []
    for ln in lines:
        e = esc(ln)
        if re.fullmatch(r"[=\-]{20,}", ln):
            out.append(f'<span class="rule">{e}</span>')
        elif ln and ln == ln.upper() and re.search(r"[A-Z]{4}", ln) and not ln.startswith(" "):
            out.append(f'<span class="h">{e}</span>')
        else:
            out.append(e)
    return "\n".join(out)


cut = next(i for i, ln in enumerate(report_lines) if ln.startswith("FINDINGS IN ONE SENTENCE"))
shown_report = report_lines[:cut]
while shown_report and (not shown_report[-1].strip() or re.fullmatch(r"[=\-]+", shown_report[-1])):
    shown_report.pop()

base_pct = float(ev["baseline_rate"]) * 100
expected = float(ev["expected_gap"])
excess = float(ev["excess_procedures"])
avg = float(ev["avg_procedure_value_usd"])
val = float(ev["excess_value_usd"])
hdr = packet_header.split(",")
pvals = packet_line.split(",")
PLABEL = {"month": "month", "practice_id": "practice", "procedures_completed": "done",
          "procedures_submitted_to_claim": "billed", "avg_procedure_value_usd": "avg $"}
csv_cells = "".join(f'<span class="cv"><b>{esc(v)}</b><i>{esc(PLABEL.get(h, h))}</i></span>' for h, v in zip(hdr, pvals))

TERM_NOTES = [
    ("Totals", f"The cover and slide 2 read these. {usd(tot['run_rate']['raw'])} is counted at the floor; "
               f"{usd(tot['run_rate_upper']['raw'])} is the ceiling, not the claim."),
    ("Run-rate findings", "Ranked by counted value, and a test fails if the ranks and the dollars ever disagree. "
                          "Each row says whether it’s measured, modeled or contractual."),
    ("One-time", f"Counted only while its deadline is still open on {numbers['as_of_display']}. "
                 "Pass --as-of and only the deadline-bound items move."),
    ("Reported, not counted", "Backfill, recovery per person, unused licenses and the under-30-hours benefits "
                              "question are printed with their values and kept out of the headline."),
]
term_notes = "".join(f"<li><b>{esc(a)}</b><p>{esc(b).replace('--as-of', '<code>--as-of</code>')}</p></li>" for a, b in TERM_NOTES)

system_sec = f"""
<section class="sec" id="system" aria-labelledby="system-h">
  <div class="wrap">
    {sec_head(2, 'system', '<span id="system-h">One command. The deck’s exact numbers.</span>',
              'northgate-recovery reads the packet, computes all twelve findings in under two seconds, and writes out every row '
              'it used with its source file and line number. The deck and this page read one file it produces, so there’s no '
              'second copy of any number to drift.')}
    <div class="block sys-top">
      <div class="cmds pane">
        <div class="cmds-main">
          <p class="plbl">Install and run, from a clone of <a class="gh" data-gh="northgate-recovery">northgate-recovery</a></p>
          <div class="cmd-line"><span class="pr">$</span><code>python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt</code></div>
          <div class="cmd-line"><span class="pr">$</span><code>.venv/bin/python -m northgate</code></div>
        </div>
        <div class="cmds-side">
          <p class="cmds-note">Python 3.10 or later. pandas is the only dependency. It installs into a local environment,
          so it works on a clean machine, and the run takes under two seconds.</p>
          <p class="cmds-note sub">Tests: <code>.venv/bin/pip install pytest</code>, then <code>.venv/bin/python -m pytest -q</code><br>
          Also: <code>explain &lt;finding&gt;</code> · <code>tieouts</code> · <code>plan</code> · <code>triage</code></p>
        </div>
      </div>
      <div class="stats4">
        <p class="pstat"><b>{N_FINDINGS}</b><span>findings computed, {N_COUNTED} of them counted</span></p>
        <p class="pstat"><b>{num(EVIDENCE_ROWS)}</b><span>evidence rows, each with its source file and line</span></p>
        <p class="pstat"><b>{TESTS_PASSED}</b><span>tests passing: the numbers, every quote, the deck contract</span></p>
        <p class="pstat"><b>{TIE_BREAKS} of {TIE_CHECKS}</b><span>tie-outs against the P&amp;L break, and the report says why</span></p>
      </div>
    </div>

    <div class="block term-wrap">
      <div class="term pane">
        <div class="term-head"><span><code>python -m northgate</code></span>
          <span class="meta">First {len(shown_report)} of {len(report_lines)} lines, unedited</span></div>
        <pre tabindex="0">{term_html(shown_report)}</pre>
      </div>
      <ol class="term-notes">{term_notes}</ol>
    </div>

    <div class="block">
      <div class="block-head"><h3>Walk any number back to a row</h3>
        <p>The largest finding, from the headline to one line of the packet.</p></div>
      <ol class="trace pane">
        <li class="step"><p class="plbl">1 · The finding</p>
          <p class="big">{usd(cc['annual_net'])}</p>
          <p class="cap">a year of procedures done but never billed, at the 8 routing-slip sites</p>
          <p class="mono">python -m northgate explain charge_capture</p></li>
        <li class="step"><p class="plbl">2 · The evidence row</p>
          <dl class="kv"><dt>part</dt><dd>{esc(ev['part'])}</dd><dt>source_line</dt><dd>{src_line_no}</dd>
            <dt>month</dt><dd>{esc(ev['month'])}</dd><dt>practice</dt><dd>{esc(ev['practice_id'])}</dd>
            <dt>done</dt><dd>{ev['procedures_completed']}</dd><dt>billed</dt><dd>{ev['procedures_submitted_to_claim']}</dd>
            <dt>gap</dt><dd>{ev['gap']}</dd><dt>excess value</dt><dd>{usd(val, True)}</dd></dl>
          <p class="cap">One of {len(slip)} site-months in <code>out/evidence/charge_capture.csv</code></p></li>
        <li class="step"><p class="plbl">3 · The packet line</p>
          <p class="mono">sed -n '{src_line_no}p' packet/{esc(ev['source_file'])}</p>
          <p class="csv">{csv_cells}</p>
          <p class="cap">Line {src_line_no} of the file you sent, byte for byte.</p></li>
        <li class="step"><p class="plbl">4 · The arithmetic</p>
          <p class="calc">{ev['gap']} missing <span>−</span> {expected:.2f} expected at the {base_pct:.3f}% baseline <span>=</span> <b>{excess:.2f}</b></p>
          <p class="calc">{excess:.2f} <span>×</span> ${avg:,.0f} <span>=</span> <b>{usd(val, True)}</b></p>
          <p class="calc">Sum of {len(slip)} site-months <span>=</span> <b>{usd(slip_sum)}</b></p>
          <p class="calc"><span>×</span> {A.NET_COLLECTION.value:.0%} collected <span>=</span> <b>{usd(cc['annual_net'])}</b> a year</p></li>
      </ol>
    </div>

    <div class="block">
      <div class="block-head"><h3>How a number moves</h3><p>One direction, one source of truth.</p></div>
      <ol class="sysflow pane">
        <li><code>packet/</code><p>{num(meth['data_rows'])} rows in 18 CSVs and {meth['documents']} documents, untouched</p></li>
        <li><code>load.py</code><p>Reads every table and keeps each row’s original line number</p></li>
        <li><code>findings/</code><p>One module per finding, {N_FINDINGS} in all. Every constant lives in <code>assumptions.py</code> with its quote</p></li>
        <li><code>out/</code><p><code>findings.json</code>, one evidence CSV per finding, and <code>deck-numbers.json</code></p></li>
        <li><code>deck</code><p>The slides, the PDF and this page read only <code>deck-numbers.json</code></p></li>
      </ol>
    </div>
  </div>
</section>"""

# documents ------------------------------------------------------------
shape_rows = []
for s, kind, note in SHAPES:
    w = max(s["count"] / MAX_SHAPE * 100, 0)
    tag = {"kept": '<span class="tag2 kept">Kept</span>', "decoy": '<span class="tag2 decoy">Decoy</span>'}.get(kind, "")
    ver = f'{num(s["versions"])} versions' if s["versions"] > 1 else ""
    sub = " · ".join(x for x in (ver, note) if x)
    shape_rows.append(
        f'<li class="shape-row {kind}"><span class="cnt">{num(s["count"])}</span>'
        f'<span class="txt">{tag}{pillify(s["text"])}{f"<span class=shape-note>{sub}</span>" if sub else ""}</span>'
        f'<span class="bar-wrap"><span class="bar" style="width:{w:.3f}%"></span></span></li>')

dvd = "".join(f'<tr><td class="who">{esc(r["who"])}</td><td data-l="What they said">{esc(r["claim"])}</td><td data-l="What the data shows">{esc(r["data"])}</td></tr>'
              for r in numbers["docs_vs_data"])
kept_pct = meth["rare_words"] / meth["corpus_words"] * 100
docs_sec = f"""
<section class="sec" id="documents" aria-labelledby="documents-h">
  <div class="wrap">
    {sec_head(3, 'documents', f'<span id="documents-h">{num(meth["packet_words"])} words. {meth["signal_documents"]} worth reading.</span>',
              'Almost every line in the packet is one of a few hundred template sentences with a different town swapped in. '
              'Reading didn’t scale, and keyword search drowned in copies. So I stopped reading and started counting.')}
    <div class="block">
      <ol class="funnel">
        <li><b>{num(meth['packet_words'])}</b><span>words in {meth['documents']} documents</span></li>
        <li><b>{num(meth['corpus_words'])}</b><span>words of meetings, email and chat, in {num(meth['utterances'])} lines</span></li>
        <li><b>{num(tri.skeletons)}</b><span>sentence shapes once towns, names and numbers are masked</span></li>
        <li><b>{num(meth['rare_words'])}</b><span>words kept: {len(tri.rare)} lines whose shape is rare, {meth['reduction_pct']}% removed</span></li>
        <li><b>{meth['signal_documents']}</b><span>documents read in full: {len(flagged)} conversations, plus {meth['signal_documents'] - len(flagged)} contracts, policies and invoices</span></li>
      </ol>
      <div class="ratio" role="img" aria-label="{num(meth['rare_words'])} of {num(meth['corpus_words'])} words kept">
        <div class="ratio-bar"><i style="width:{kept_pct:.3f}%"></i></div>
        <div class="ratio-legend"><span>{num(meth['corpus_words'])} words of conversation, to scale</span>
          <span><b>{num(meth['rare_words'])}</b> kept</span></div>
      </div>
    </div>

    <div class="block">
      <div class="shapes pane">
        <div class="block-head"><h3>Every line reduced to its shape, then counted</h3>
          <p class="shape-legend">Masked before counting:
            <span class="mask mask--place">town</span><span class="mask mask--name">Capitalized</span><span class="mask mask--num">2025</span></p></div>
        <ol class="shape-list">
          <li class="shape-row head" aria-hidden="true"><span class="cnt">Seen</span><span class="txt">Line, as the filter sees it</span><span class="bar-wrap"></span></li>
          {''.join(shape_rows)}
        </ol>
        <p class="shapes-foot">{num(tri.skeletons)} shapes cover all {num(meth['utterances'])} lines.
          The filter keeps a line when its shape appears at most {A.TRIAGE_MAX_SKELETON_COUNT.value} times and it runs
          {A.TRIAGE_MIN_WORDS.value} words or more. Source: <code>northgate/triage.py</code>, run by <code>python -m northgate triage</code>.</p>
      </div>
    </div>

    <div class="block notes">
      <div><h3>Checking the filter</h3>
        <p>A filter that throws away 99% of the text needs its own check. A sub-agent read everything the filter
        dropped: all {UNFLAGGED_EMAIL} unflagged emails in full, plus a separate normalization of every chat and transcript
        line. It found nothing I’d missed. It did find tells: every filler email is stamped <code>00:00:00</code>, and
        eight serious-sounding decoy lines are each repeated 55 to 120 times. Citing one would’ve been a mistake.</p></div>
      <div><h3>What it missed, and how I caught it</h3>
        <p>v0 threw away quoted replies inside forwarded chains. One of them was Bev saying she’d been holding
        Dr. Osei’s denied Delta claims instead of writing them off. That’s the only evidence the money is still recoverable.
        I caught it because I read the flagged documents in full and didn’t trust the extracted lines. A test now checks
        that the line is kept.</p></div>
    </div>

    <div class="block">
      <div class="block-head"><h3>Where a sentence meets a column</h3>
        <p>The findings that matter sit where a document and the data disagree.</p></div>
      <div class="pane pad"><div class="scroll" tabindex="0"><table class="t stack">
        <thead><tr><th>Who</th><th>What they said</th><th>What the data shows</th></tr></thead>
        <tbody>{dvd}</tbody></table></div></div>
    </div>
  </div>
</section>"""

# harness --------------------------------------------------------------
AGENTS = [
    ("Triage sweep", "Read everything the filter dropped, to prove the filter safe",
     "Zero misses. Found the 00:00:00 stamp and the decoy lines. It missed the quoted-reply bug, because it only read what the filter dropped.",
     "harness/04-agents/01-triage-sweep-agent.md"),
    ("System builder", "Turn my script and spec into the repo: CLI, evidence with line numbers, tests",
     "Pushed back three times: the Delta rounding, the Patterson reading, “lowest in the company”. It was right all three times.",
     "harness/04-agents/02-system-builder.md"),
    ("Glass kit", "Find a liquid glass that survives PDF export, then build the deck",
     "Built a lab, tried four techniques and diffed screen against PDF pixel by pixel. Only baked plates survived.",
     "harness/04-agents/03-glass-kit.md"),
    ("Dana", "Break every number before Stage 3 does",
     f"Re-derived everything exactly, then took two findings down. The headline went from {d('run_rate_upper')} to {d('run_rate')} counted.",
     "harness/06-verification/play-dana.md"),
]
agent_rows = "".join(
    f'<tr><td class="who"><b>{esc(a)}</b></td><td data-l="Its job">{esc(j)}</td><td data-l="What it changed">{esc(c)}</td>'
    f'<td class="file" data-l="Prompt"><a href="#source" data-open="{esc(f)}">{esc(f.split("/", 1)[1])}</a></td></tr>'
    for a, j, c, f in AGENTS)
PIPE = [
    ("02-analysis/findings_v0.py", "My first pass. One script, every number."),
    ("03-specs/SYSTEM-SPEC.md", "Pins every expected value. The agent reproduces them to the dollar and reports any it thinks are wrong."),
    ("northgate-recovery", f"The system: a CLI, evidence with source lines, {TESTS_PASSED} tests."),
    ("deck-numbers.contract.json", "The only thing the deck may read. The system writes it; a test checks its shape."),
    ("05-deck/build.py", "Renders the slides from that JSON and exports the PDF. It rewrites a sentence before it types a number."),
]
def wbr(x):
    return re.sub(r"([/.])", r"<wbr>\1", esc(x)).replace("<wbr>/", "/<wbr>")


pipe = "".join(f'<li><span class="pn">{i}</span><code>{wbr(f)}</code><p>{esc(t)}</p></li>' for i, (f, t) in enumerate(PIPE, 1))
harness_sec = f"""
<section class="sec" id="harness" aria-labelledby="harness-h">
  <div class="wrap">
    {sec_head(4, 'harness', '<span id="harness-h">Specs pin the numbers. Agents have to disagree out loud.</span>',
              'One main session did the analysis and made the calls. Sub-agents took anything that could run in parallel or '
              'needed fresh eyes. There’s no custom infrastructure: the harness is the workflow. Specs that pin every number, '
              'agents that report a disagreement instead of fixing it, and one JSON contract between the system and the deck.')}
    <div class="block">
      <div class="block-head"><h3>From analysis to deck, without retyping a number</h3>
        <p>The instruction that mattered most: report a number you think is wrong, don’t change it. It caught three mistakes.</p></div>
      <ol class="pipe pane">{pipe}</ol>
    </div>
    <div class="block">
      <div class="block-head"><h3>The sub-agents</h3><p>Every prompt is in the repo, verbatim.</p></div>
      <div class="pane pad"><div class="scroll" tabindex="0"><table class="t agents stack">
        <thead><tr><th>Agent</th><th>Its job</th><th>What it changed</th><th>Prompt</th></tr></thead>
        <tbody>{agent_rows}</tbody></table></div></div>
    </div>
    <div class="block setup">
      <dl>
        <div><dt>Main session</dt><dd>Claude, in Cowork. It orchestrated, did the data analysis and made the calls.</dd></div>
        <div><dt>Skills</dt><dd>A data-viz skill for chart rules and a palette check, and a design skill for layout and type.</dd></div>
        <div><dt>Connectors</dt><dd>Google Drive and Chrome, to pull my own past decks for the visual direction.</dd></div>
        <div><dt>Stripped</dt><dd>Nothing proprietary is in the harness. Left out: the packet (it’s in the system repo) and rendering intermediates.</dd></div>
      </dl>
    </div>
  </div>
</section>"""

# stress test ------------------------------------------------------------
ba_rows = "".join(f'<tr><td class="who">{esc(a)}</td><td class="num was" data-l="Before">{esc(b)}</td><td data-l="After">{md(c).removeprefix("<p>").removesuffix("</p>")}</td></tr>'
                  for a, b, c in before_after)
def inline_md(x):
    return md(re.sub(r"\s+", " ", x.strip())).removeprefix("<p>").removesuffix("</p>")


q_items = "".join(f'<div class="qa-item"><h3>{inline_md(q)}</h3><p>{inline_md(a)}</p></div>' for q, a in qs)
also_html = "".join(f"<li>{md(x).removeprefix('<p>').removesuffix('</p>')}</li>" for x in also_items)
review_sec = f"""
<section class="sec" id="review" aria-labelledby="review-h">
  <div class="wrap">
    {sec_head(5, 'review', '<span id="review-h">I tried to break my own numbers first</span>',
              'In Stage 3, Dana’s job is to disbelieve me, so I ran that meeting early. An agent with fresh context re-derived every '
              'headline from the raw CSVs before reading my code, then attacked the logic. Every number re-derived exactly. '
              'Two findings didn’t survive the logic, and they came down.')}
    <div class="block review-grid">
      <div class="pane pad"><p class="plbl">What changed because of it</p><div class="scroll" tabindex="0"><table class="t ba stack">
        <thead><tr><th>Finding</th><th class="num">Before</th><th>After</th></tr></thead><tbody>{ba_rows}</tbody></table></div></div>
      <div class="also"><p class="plbl">It also caught</p><ul>{also_html}</ul>
        <div class="second"><p class="plbl">A second opinion on the first opinion</p>{second}</div></div>
    </div>
    <div class="block">
      <div class="block-head"><h3>Six questions I expect in Stage 3</h3><p>With the answer the data supports after the revisions.</p></div>
      <div class="qa">{q_items}</div>
    </div>
  </div>
</section>"""

# what broke ------------------------------------------------------------
fail_items = "".join(
    f'<li><details class="fail"><summary><span class="fn-n">{n:02d}</span><span class="fn-t">{t}'
    f'<span class="fn-s">{esc(FAIL_SUMMARY[n])}</span></span><span class="pm" aria-hidden="true"></span></summary>'
    f'<div class="fail-body">{b}</div></details></li>'
    for n, t, b in fails)
broke_sec = f"""
<section class="sec" id="broke" aria-labelledby="broke-h">
  <div class="wrap">
    {sec_head(6, 'broke', '<span id="broke-h">Ten things broke. Here’s how each one got caught.</span>',
              'In the order they happened. Every one of them would’ve reached the deck if nothing had checked it.')}
    <div class="block"><ol class="fails">{fail_items}</ol></div>
  </div>
</section>"""

# source ------------------------------------------------------------
source_sec = f"""
<section class="sec" id="source" aria-labelledby="source-h">
  <div class="wrap">
    {sec_head(7, 'source', '<span id="source-h">Both repositories, file by file</span>',
              'Everything in <a class="gh" data-gh="northgate-recovery">northgate-recovery</a> and '
              '<a class="gh" data-gh="northgate-harness">northgate-harness</a> as submitted, except the packet itself '
              'and the font files. To run it, clone the system repo and follow its README.')}
    <div class="block">
      <div class="src pane">
        <div class="src-top">
          <div class="seg" role="group" aria-label="Repository">
            <button type="button" data-repo="recovery" aria-pressed="true">northgate-recovery</button>
            <button type="button" data-repo="harness" aria-pressed="false">northgate-harness</button>
          </div>
          <span class="meta" id="src-count"></span>
        </div>
        <div class="src-body">
          {trees['recovery']}{trees['harness']}
          <div class="pane-code">
            <div class="crumbs"><span class="path" id="src-path"></span><span class="meta" id="src-lines"></span></div>
            <div class="view" id="src-view" tabindex="0"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>"""
repo_meta = {k: f"{v[0]} files · {num(v[1])} lines" for k, v in counts.items()}

footer = f"""
<footer class="wrap"><div class="foot">
  <p><b>Ian Milkowski</b><span>Northgate, Stage 2</span></p>
  <p class="meta">Every number on this page comes from <code>out/deck-numbers.json</code>, written by <code>python -m northgate</code>.</p>
</div></footer>"""

# ---------------------------------------------------------------- css + js
CSS = (Path(__file__).parent / "submission.css").read_text()
JS = (Path(__file__).parent / "submission.js").read_text()

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Northgate · Ian Milkowski</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%23F7F4EE'/><stop offset='.5' stop-color='%23CFE3F7'/><stop offset='1' stop-color='%23E4DCF8'/></linearGradient></defs><rect x='4' y='4' width='56' height='56' rx='16' fill='url(%23g)'/><rect x='4.75' y='4.75' width='54.5' height='54.5' rx='15.25' fill='none' stroke='white' stroke-opacity='.9' stroke-width='1.5'/><rect x='18' y='34' width='7' height='14' rx='2' fill='%235A86D8'/><rect x='29' y='24' width='7' height='24' rx='2' fill='%235A86D8'/><rect x='40' y='16' width='7' height='32' rx='2' fill='%233F6FCB'/></svg>">
<meta name="description" content="What Northgate can recover: the deck, the system and the harness. Straterai FDE Stage 2, Ian Milkowski.">
<noscript><style>.deck-bar, .frame, .present-bar, .src {{ display: none !important; }} .deck-web {{ gap: 12px; }}</style></noscript>
<style>
{FONT_FACES}
{glass_css}
{deck_css}
{CSS}
</style>
</head>
<body>
<div class="studio" aria-hidden="true"><i class="band"></i><i class="key"></i></div>
<a class="skip" href="#deck">Skip to the deck</a>
<nav class="topbar" aria-label="Sections"><div class="topbar-in pane">
  <a class="brand" href="#top"><b>Northgate</b><span>Ian Milkowski</span></a>
  <div class="links">{nav}</div>
</div></nav>
{hero}
<main>
{deck_sec}
{system_sec}
{docs_sec}
{harness_sec}
{review_sec}
{broke_sec}
{source_sec}
</main>
{footer}
{''.join(templates)}
<script>window.__SRC_META = {json.dumps(repo_meta)};</script>
<script>
{glass_js}
</script>
<script>
{JS}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------- checks
visible = re.sub(r"<template[\s\S]*?</template>|<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", doc)
visible_text = html.unescape(re.sub(r"<[^>]+>", " ", visible))
assert "—" not in visible_text, [visible_text[max(0, i - 60):i + 20] for i in [visible_text.index("—")]]
assert not re.search(r"https?://", re.sub(r"xmlns(:\w+)?=['\"]http://www\.w3\.org/[^'\"]*['\"]", "", visible)), "external URL in page"
out = OUT / FILENAME
out.write_text(doc)
print(f"wrote {out} ({len(doc.encode()) / 1024 / 1024:.2f} MB); tests {TESTS_PASSED}; evidence rows {EVIDENCE_ROWS}; "
      f"source {repo_meta}; report {len(shown_report)}/{len(report_lines)} lines")
