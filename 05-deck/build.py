#!/usr/bin/env python3
"""
build.py · "Northgate: what's recoverable" (15 slides, 1920x1080, PDF + HTML)

    python3 build.py                              # numbers: the real file if it is ready, else the example
    python3 build.py --numbers real --wait 3600   # wait (up to an hour) for the real file, then build
    python3 build.py --numbers example            # build against the contract example
    python3 build.py --slides 1,3 --quick         # a few slides, screens only (design iteration)

Every figure comes from deck-numbers.json through N(path); a key that is missing is reported, never
invented. The deck is written to out/deck.html (+ out/deck.css, out/kit/, out/fonts/), checked for
text collisions, clipping and 8% horizontal slack, then rendered through the glass kit's baked
pipeline: out/Northgate-Recoverable.pdf, out/png/slide-NN@1x.png and out/contact-sheet.png.
Fonts: Inter + Inter Tight from /home/claude/deck/fonts-inter/ (any file names, zips included,
matched by family name) when present, otherwise the kit's Instrument Sans stand-in.
"""
import argparse, datetime as dt, html, importlib.util, json, re, shutil, sys, time, zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

DECK = Path(__file__).resolve().parent
KIT = DECK / "glass-kit"
OUT = DECK / "out"
REAL = Path("/home/claude/northgate-recovery/out/deck-numbers.json")
EXAMPLE = DECK / "deck-numbers.example.json"
FONTS_INTER = DECK / "fonts-inter"
READY_RUN_RATE = 1330073
W, H = 1920, 1080
TOTAL = 15

# ---------------------------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------------------------
class Numbers:
    """N('findings[0].annual.display') -> value. Missing keys are recorded and rendered visibly."""
    def __init__(self, data, path):
        self.d, self.path, self.missing = data, path, []

    def __call__(self, path):
        cur = self.d
        for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
            try:
                cur = cur[int(part[1:-1])] if part.startswith("[") else cur[part]
            except (KeyError, IndexError, TypeError):
                if path not in self.missing:
                    self.missing.append(path)
                return f"[missing: {path}]"
        return cur

    def gap(self, what):
        """A figure the copy needs that the JSON does not carry: record it; the caller words around it."""
        if what not in self.missing:
            self.missing.append(what)


def real_ready():
    try:
        d = json.loads(REAL.read_text())
    except Exception:
        return False, None
    return "run_rate_upper" in d.get("totals", {}), d   # current schema (round 3) is present


def load_numbers(choice, wait):
    if choice == "example":
        return Numbers(json.loads(EXAMPLE.read_text()), EXAMPLE)
    if choice not in ("real", "auto"):
        p = Path(choice)
        return Numbers(json.loads(p.read_text()), p)
    deadline = time.time() + wait
    while True:
        ok, d = real_ready()
        if ok:
            return Numbers(d, REAL)
        if choice == "auto" and time.time() >= deadline:
            print(f"numbers: {REAL} not ready; building against the example")
            return Numbers(json.loads(EXAMPLE.read_text()), EXAMPLE)
        if time.time() >= deadline:
            sys.exit(f"numbers: {REAL} still not ready after {wait}s")
        print(f"numbers: waiting for {REAL} (totals.run_rate.raw == {READY_RUN_RATE}) ...", flush=True)
        time.sleep(20)


# ---------------------------------------------------------------------------------------------
# formatting (display strings from the JSON are used as-is; these only format raw values)
# ---------------------------------------------------------------------------------------------
MINUS = "\u2212"
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def rhu(x, dp=0):
    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP))


def money(raw, sentence=False):
    """The contract's display rules. sentence=True: one decimal for thousands below $100K (never '.0')."""
    if isinstance(raw, str):
        return raw
    a, sign = abs(raw), (MINUS if raw < 0 else "")
    if a >= 1_000_000:
        s = f"${rhu(a / 1e6, 2):.2f}M"
    elif a >= 1_000:
        if sentence and a < 100_000:
            s = f"${rhu(a / 1e3, 1):.1f}".rstrip("0").rstrip(".") + "K"
        else:
            s = f"${rhu(a / 1e3):.0f}K"
    else:
        s = f"${rhu(a):.0f}"
    return sign + s


def money_axis(raw):
    """Axis bounds: $0, $1M, $1.75M, $2.5M."""
    if raw >= 1_000_000:
        return "$" + f"{raw / 1e6:.2f}".rstrip("0").rstrip(".") + "M"
    return money(raw)


def pct_keep(x):
    """'Percent display keeps the dp shown': 4.0 -> 4.0%, 21.7 -> 21.7%, 2.422 -> 2.422%, 0 -> 0%."""
    if isinstance(x, str):
        return x
    if x == 0:
        return "0%"
    return f"{x}%"


def intc(n):
    return f"{int(n):,}" if not isinstance(n, str) else n


def ymd(s):
    return dt.date.fromisoformat(s)


def md(s):
    d = ymd(s)
    return f"{MONTHS[d.month - 1]} {d.day}"


def mdy(s):
    d = ymd(s)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def word(n, cap=False):
    w = WORDS.get(n, str(n))
    return w.capitalize() if cap else w


def esc(s):
    return html.escape(str(s), quote=False)


def dots(s):
    """HTML: ' · ' inside data text -> the chrome's separator span (escaped)."""
    return sep().join(esc(x) for x in str(s).split(" · "))


def sdots(s):
    """SVG text: ' · ' -> en spaces around the dot (no spans needed)."""
    return esc(str(s).replace(" · ", "\u2002·\u2002"))


def smart(s):
    """Typographic apostrophes/quotes for display copy (content unchanged)."""
    s = re.sub(r"(\w)'(\w)", "\\1\u2019\\2", str(s))
    s = re.sub(r"'", "\u2019", s)
    return s


# ---------------------------------------------------------------------------------------------
# fonts: Inter + Inter Tight from fonts-inter/ (matched by family name), else the stand-in
# ---------------------------------------------------------------------------------------------
def _face_info(path):
    from fontTools.ttLib import TTFont
    try:
        f = TTFont(str(path), lazy=True, fontNumber=0)
    except Exception:
        return None
    nm = f["name"]
    fam = (nm.getDebugName(16) or nm.getDebugName(1) or "").strip()
    sub = (nm.getDebugName(17) or nm.getDebugName(2) or "").strip()
    os2 = f["OS/2"]
    return {"path": Path(path), "family": re.sub(r"\s+", " ", fam), "sub": sub, "weight": os2.usWeightClass,
            "italic": bool(os2.fsSelection & 1) or "italic" in sub.lower(), "variable": "fvar" in f}


def discover_fonts(log=print):
    """Returns {'source': ..., 'faces': {('text'|'display', weight): path}} and copies files to out/fonts/."""
    faces = []
    if FONTS_INTER.is_dir():
        cache = OUT / "_fonts-inter"
        for z in FONTS_INTER.rglob("*.zip"):
            try:
                with zipfile.ZipFile(z) as zf:
                    for m in zf.namelist():
                        if m.lower().endswith((".ttf", ".otf")) and "__macosx" not in m.lower():
                            dst = cache / z.stem / m
                            if not dst.exists():
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                dst.write_bytes(zf.read(m))
            except zipfile.BadZipFile:
                log(f"fonts: {z.name} is not a readable zip")
        for p in list(FONTS_INTER.rglob("*")) + (list(cache.rglob("*")) if cache.exists() else []):
            if p.suffix.lower() in (".ttf", ".otf"):
                info = _face_info(p)
                if info and not info["italic"]:
                    faces.append(info)

    def fam_key(f):
        return f["family"].lower()

    def is_tight(f):
        return fam_key(f) == "inter tight"

    def inter_rank(f):  # text optical size preferred at 20-40px on a 1920 slide
        k = fam_key(f)
        order = ["inter 24pt", "inter", "inter 18pt", "inter 28pt"]
        return order.index(k) if k in order else None

    def pick(cands, weight):
        stat = [f for f in cands if not f["variable"]]
        exact = [f for f in stat if f["weight"] == weight]
        if exact:
            return exact[0]["path"], weight
        var = [f for f in cands if f["variable"]]
        if var:
            return var[0]["path"], weight
        if stat:
            best = min(stat, key=lambda f: abs(f["weight"] - weight))
            return best["path"], best["weight"]
        return None, None

    chosen = {}
    tight = [f for f in faces if is_tight(f)]
    inter = sorted([f for f in faces if inter_rank(f) is not None], key=inter_rank)
    if inter:
        best_family = fam_key(inter[0])
        inter = [f for f in inter if fam_key(f) == best_family]
    if tight and inter:
        for w in (400, 500, 600):
            chosen[("text", w)] = pick(inter, w)
        for w in (500, 600):
            chosen[("display", w)] = pick(tight, w)
    if chosen and all(v[0] for v in chosen.values()):
        src = f"Inter ({fam_key(inter[0])}) + Inter Tight from {FONTS_INTER}"
    else:
        if FONTS_INTER.is_dir():
            pass
        st = KIT / "fonts"
        chosen = {("text", 400): (st / "InstrumentSans-Regular.ttf", 400), ("text", 500): (st / "InstrumentSans-Medium.ttf", 500),
                  ("text", 600): (st / "InstrumentSans-SemiBold.ttf", 600), ("display", 500): (st / "InstrumentSans-Medium.ttf", 500),
                  ("display", 600): (st / "InstrumentSans-SemiBold.ttf", 600)}
        src = "Instrument Sans (OFL), embedded; 500/600 interpolated from the 400/700 masters"
    return {"source": src, "faces": chosen, "inter": src.startswith("Inter")}


def font_css(fonts):
    """@font-face rules for the chosen files (copied into out/fonts/). Declared after glass.css, so they win."""
    if not fonts["inter"]:
        return "/* Type: Instrument Sans, declared in kit/glass.css */\n"
    dst = OUT / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    rules = []
    for (role, w), (path, _) in sorted(fonts["faces"].items()):
        fam = "Inter" if role == "text" else "Inter Tight"
        name = f"{fam.replace(' ', '')}-{w}{path.suffix.lower()}"
        shutil.copy2(path, dst / name)
        fmt = "opentype" if path.suffix.lower() == ".otf" else "truetype"
        rules.append(f'@font-face {{ font-family: "{fam}"; font-style: normal; font-weight: {w}; font-display: block; '
                     f'src: url("fonts/{name}") format("{fmt}"); }}')
    return "\n".join(rules) + "\n"


class Metrics:
    """Advance-width text measurement with the chosen font files (layout decisions; the browser checks the rest)."""
    def __init__(self, fonts):
        from fontTools.ttLib import TTFont
        self.f = {}
        for key, (path, _) in fonts["faces"].items():
            t = TTFont(str(path), lazy=True)
            self.f[key] = (t.getBestCmap(), t["hmtx"].metrics, t["head"].unitsPerEm)

    def width(self, text, size, role="text", weight=400, ls=0.0):
        key = (role, weight) if (role, weight) in self.f else min(self.f, key=lambda k: (k[0] != role, abs(k[1] - weight)))
        cmap, hmtx, upm = self.f[key]
        adv = 0
        for ch in str(text):
            g = cmap.get(ord(ch)) or cmap.get(0x20)
            adv += hmtx.get(g, (upm // 2, 0))[0]
        return adv / upm * size + ls * size * max(len(str(text)) - 1, 0)


# ---------------------------------------------------------------------------------------------
# deck CSS (layout only: tokens, field, glass and type scale come from the kit)
# ---------------------------------------------------------------------------------------------
DECK_CSS = r"""
/* ---- chrome: identical on every slide ---- */
.eyebrow { position: absolute; left: 120px; top: 96px; height: 28px; display: flex; align-items: center; gap: 16px; white-space: nowrap; }
.sep { padding: 0 .5em; }
.eyebrow .sep { color: var(--ink-3); }
.source { position: absolute; left: 120px; bottom: 84px; margin: 0; white-space: nowrap; }
.page-pill { right: 120px; bottom: 74px; width: 104px; justify-content: center; }
.page-pill .of { color: var(--ink-2); }

/* ---- hero slides: number and line share a baseline; the line starts on column 7 ---- */
.headline { position: absolute; left: 120px; top: 138px; width: 1680px; display: grid;
  grid-template-columns: 852px 828px; align-items: last baseline; }
.headline .t-hero { white-space: nowrap; margin-left: -9px; }
.headline .t-heroline { text-wrap: balance; }

/* ---- title slides ---- */
.titleblock { position: absolute; left: 120px; top: 138px; width: 1680px; }
.titleblock .t-title { text-wrap: balance; }

/* ---- the proof slab and what sits under it ---- */
.slab { left: 120px; width: 1680px; }
.under { position: absolute; left: 120px; width: 1680px; }
.quote { font: 400 24px/34px var(--font-text); --ls: -.004em; color: var(--ink-2); margin: 0; }
.quote .who { color: var(--ink-3); }

/* ---- charts: plain SVG, to scale, directly labelled ---- */
.chart { display: block; overflow: visible; }
.chart text { font-family: var(--font-text); font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; dominant-baseline: central; }
.chart .c-label { font-size: 20px; font-weight: 500; fill: var(--ink); }
.chart .c-sub { font-size: 18px; font-weight: 400; fill: var(--ink-2); }
.chart .c-value { font-family: var(--font-display); font-size: 24px; font-weight: 600; fill: var(--ink); --ls: -.01em; }
.chart .c-ref { font-size: 20px; font-weight: 500; fill: var(--ink-2); }
.chart .c-ref-v { font-family: var(--font-display); font-weight: 600; fill: var(--ink); }
.chart .c-axis { font-size: 18px; font-weight: 400; fill: var(--ink-3); }
.chart .mark { fill: var(--data-blue); }
.chart .mark.em { fill: var(--data-blue-deep); }
.chart .ref { stroke: var(--data-violet); stroke-width: 2; }
.chart .zero { stroke: var(--hairline); stroke-width: 1.5; }

/* ---- tables inside a slab ---- */
.tbl { width: 100%; border-collapse: collapse; }
.tbl th { font: 500 18px/24px var(--font-text); color: var(--ink-2); text-align: left; padding: 0 0 10px; white-space: nowrap; }
.tbl td { font: 400 24px/32px var(--font-text); color: var(--ink); padding: 12px 0; border-top: 1px solid var(--hairline); vertical-align: middle; }
.tbl th.r, .tbl td.r { text-align: right; }
.tbl td.num { font-family: var(--font-display); font-weight: 600; font-size: 24px; --ls: -.01em; }
.tbl td.soft { color: var(--ink-2); }
.tbl tr.total td { border-top: 1.5px solid rgba(24, 32, 46, .30); font-weight: 600; }
.tbl .gap { width: 40px; }
.tbl .tag { vertical-align: 2px; margin-left: 12px; }
.tbl .aside { font-size: 18px; color: var(--ink-3); margin-left: 14px; }

.answer-t td { padding: 17px 0; }
.answer-t td.ttl { padding-right: 32px; white-space: nowrap; }
.answer-t td.rank { font-family: var(--font-display); font-weight: 600; color: var(--ink-2); }
.answer-t td.cash { font-weight: 500; }
.answer-t th.key { color: var(--ink); }
.answer-t td svg { display: block; }

/* ---- quiet stats, callouts and notes ---- */
.stats { position: absolute; left: 120px; width: 1680px; display: flex; gap: 72px; margin: 0; white-space: nowrap; }
.stats p { margin: 0; font: 400 24px/32px var(--font-text); color: var(--ink-2); }
.stats b { font-family: var(--font-display); font-weight: 600; color: var(--ink); --ls: -.012em; }
.callout { font: 500 26px/36px var(--font-text); --ls: -.01em; color: var(--ink); margin: 0; text-wrap: pretty; }
.note { font: 400 24px/34px var(--font-text); --ls: -.004em; color: var(--ink-2); margin: 0; text-wrap: pretty; }
.nb { white-space: nowrap; }
.tbl td { text-wrap: pretty; }
.under .note + .note, .under .callout + .note { margin-top: 10px; }

/* ---- side column (slides 10, 12) ---- */
.side { position: absolute; left: 1296px; width: 504px; }
.side .st { padding: 0 0 22px; margin: 0 0 22px; border-bottom: 1px solid var(--hairline); }
.side .st:last-child { border-bottom: 0; }
.side .big { font: 400 26px/36px var(--font-text); --ls: -.01em; color: var(--ink); margin: 0; text-wrap: balance; }
.side .big b { font-family: var(--font-display); font-weight: 600; --ls: -.02em; }
.side .small { font: 400 22px/32px var(--font-text); color: var(--ink-2); margin: 6px 0 0; text-wrap: pretty; }

/* ---- work table (11) and list (13) ---- */
.tbl.work td { font-size: 22px; line-height: 30px; padding: 16px 28px 16px 0; vertical-align: top; }
.tbl.work th { padding-right: 28px; }
.tbl.work td.role { font-weight: 500; }
.tbl.work td.role .n { color: var(--ink-2); font-weight: 400; }
.list { display: grid; grid-template-columns: 1fr 1fr; column-gap: 64px; }
.list .it { border-top: 1px solid var(--hairline); padding: 16px 0 17px; }
.list .it:nth-child(-n+2) { border-top: 0; padding-top: 0; }
.list .it h3 { font: 500 24px/32px var(--font-text); --ls: -.01em; color: var(--ink); margin: 0; }
.list .it p { font: 400 20px/28px var(--font-text); color: var(--ink-2); margin: 4px 0 0; text-wrap: pretty; }

/* ---- method (15) ---- */
.flow .stat { margin: 0; }
.flow .stat .v { display: block; font: 600 48px/54px var(--font-display); --ls: -.03em; color: var(--ink); }
.flow .stat .d { display: block; font: 400 22px/30px var(--font-text); color: var(--ink-2); margin-top: 4px; text-wrap: pretty; }
.flow .arrow { font: 400 24px/1 var(--font-text); color: var(--ink-3); margin: 14px 0 14px 4px; }
.dvd { position: absolute; left: 756px; width: 1044px; }
.dvd h3 { font: 500 24px/32px var(--font-text); --ls: -.01em; color: var(--ink); margin: 0 0 14px; }
.tbl.dvd-t td { font-size: 20px; line-height: 27px; padding: 11px 22px 11px 0; vertical-align: top; }
.tbl.dvd-t td.who { color: var(--ink-2); }
.cmd { position: absolute; left: 120px; display: flex; align-items: center; gap: 16px; }
.cmd .lbl { font: 400 22px/30px var(--font-text); color: var(--ink-2); }
.cmd .glass { position: relative; height: 48px; padding: 0 20px; display: inline-flex; align-items: center;
  font: 500 22px/1 var(--font-text); color: var(--ink); --glass-radius: 24px; }
.chain { font: 400 30px/40px var(--font-text); --ls: -.012em; color: var(--ink-2); margin: 0; white-space: nowrap; }
.chain b { font-family: var(--font-display); font-weight: 600; color: var(--ink); --ls: -.015em; }
.chain .op { color: var(--ink-3); padding: 0 .18em; }

/* ---- cover ---- */
.cover-title { position: absolute; left: 112px; top: 196px; }
.cover-sub { position: absolute; left: 120px; top: 460px; width: 700px; margin: 0; font: 400 30px/42px var(--font-text); --ls: -.01em; color: var(--ink-2); text-wrap: balance; }
.cover-slab { left: 960px; top: 372px; width: 840px; padding: 44px 60px 48px; }
.cover-slab .t-hero { display: block; margin-left: -8px; white-space: nowrap; }
.cover-line { font: 400 34px/44px var(--font-text); --ls: -.01em; color: var(--ink-2); margin: 10px 0 0; }
.cover-rule { height: 1px; background: rgba(24, 32, 46, .12); margin: 32px 0 26px; }
.cover-once { font: 400 30px/40px var(--font-text); --ls: -.01em; color: var(--ink); margin: 0; }
.cover-once b { font-family: var(--font-display); font-weight: 600; --ls: -.015em; }
.cover-meta { font: 400 20px/28px var(--font-text); color: var(--ink-2); }
"""

# ---------------------------------------------------------------------------------------------
# shared slide pieces
# ---------------------------------------------------------------------------------------------
def sep():
    return '<span class="sep">·</span>'


def eyebrow(text, tag=None):
    parts = [esc(x) for x in text.split(" · ")]
    t = f'<span class="t-eyebrow">{sep().join(parts)}</span>'
    if tag:
        t += f'<span class="tag">{esc(tag)}</span>'
    return f'<div class="eyebrow">{t}</div>'


def source(text):
    return f'<p class="source t-source">{sep().join(esc(x) for x in text.split(" · "))}</p>'


def pill(n):
    return f'<div class="glass glass--pill page-pill t-label"><span>{n:02d} <span class="of">/ {TOTAL}</span></span></div>'


def fid(N, i):
    return next(x for x in N("findings") if x["id"] == i)


def slide(n, body, cls=""):
    return f'<section class="slide {cls}" id="s{n:02d}" data-n="{n}">\n  <div class="field"></div>\n{body}\n  {pill(n)}\n</section>'


def headline(hero, line):
    return (f'<div class="headline"><div class="t-hero">{esc(hero)}</div>'
            f'<p class="t-heroline">{esc(smart(line))}</p></div>')


def rbar(x, y, length, t, r=4):
    """Horizontal bar: square at the baseline, 4px rounded data-end."""
    r = min(r, length / 2, t / 2)
    x1 = x + length
    return (f"M{x:.2f} {y:.2f}H{x1 - r:.2f}A{r} {r} 0 0 1 {x1:.2f} {y + r:.2f}"
            f"V{y + t - r:.2f}A{r} {r} 0 0 1 {x1 - r:.2f} {y + t:.2f}H{x:.2f}Z")


# ---------------------------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------------------------
def chart_sites(M, sites, base, ref_name, w, h):
    """S3: unbilled share by site, to scale from 0, a violet reference rule at the baseline."""
    names = [s["name"] for s in sites]
    vals = [s["gap_pct"] for s in sites]
    vtxt = [pct_keep(v) for v in vals]
    lw = max(M.width(n, 20, "text", 500) for n in names) * 1.08
    x0 = round(lw + 24)
    vw = max(M.width(t, 24, "display", 600) for t in vtxt) * 1.08
    scale = (w - x0 - 16 - vw) / max(vals)
    head, bar = 48, 24
    pitch = (h - head) / len(sites)
    xr = x0 + base * scale
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
         f'aria-label="Unbilled share of procedures by site, with the {esc(ref_name)} reference">']
    o.append(f'<line class="zero" x1="{x0 - .75}" y1="{head - 10}" x2="{x0 - .75}" y2="{h}"/>')
    o.append(f'<line class="ref" x1="{xr:.1f}" y1="{head - 14}" x2="{xr:.1f}" y2="{h}"/>')
    o.append(f'<text class="c-ref" x="{xr + 12:.1f}" y="{head / 2 - 6}">{esc(ref_name)}'
             f'<tspan class="c-ref-v" dx="10">{pct_keep(round(base, 1))}</tspan></text>')
    for i, (n, v, t) in enumerate(zip(names, vals, vtxt)):
        cy = head + pitch * (i + .5)
        y = round(cy - bar / 2)
        L = v * scale
        o.append(f'<g><title>{esc(n)}: {t}</title><text class="c-label" x="{x0 - 20}" y="{cy:.1f}" text-anchor="end">{esc(n)}</text>'
                 f'<path class="mark" d="{rbar(x0, y, L, bar)}"/>'
                 f'<text class="c-value" x="{x0 + L + 14:.1f}" y="{cy:.1f}">{t}</text></g>')
    o.append("</svg>")
    return "".join(o)



def chart_pair(M, rows, w, h, fmt, label_size=20):
    """Two or three horizontal bars to scale from 0; label above each bar, value at the tip.
    rows: [(label, value, emphasised)]"""
    vals = [r[1] for r in rows]
    vtxt = [fmt(v) for v in vals]
    vw = max(M.width(t, 26, "display", 600) for t in vtxt) * 1.08
    scale = (w - 18 - vw) / max(vals)
    n = len(rows)
    bar = 28
    lab_h = label_size + 14
    pitch = h / n
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">']
    o.append(f'<line class="zero" x1=".75" y1="4" x2=".75" y2="{h - 4}"/>')
    for i, (lab, v, em) in enumerate(rows):
        top = pitch * i + (pitch - lab_h - bar) / 2
        y = round(top + lab_h)
        L = v * scale
        o.append(f'<g><title>{esc(lab)}: {vtxt[i]}</title>'
                 f'<text class="c-label" x="0" y="{top + label_size / 2 + 2:.1f}" style="font-size:{label_size}px">{sdots(smart(lab))}</text>'
                 f'<path class="mark{" em" if em else ""}" d="{rbar(1.5, y, L, bar)}"/>'
                 f'<text class="c-value" x="{L + 16:.1f}" y="{y + bar / 2:.1f}" style="font-size:26px">{vtxt[i]}</text></g>')
    o.append("</svg>")
    return "".join(o)


def chart_ladder(M, tiers, markers, w, h):
    """S6: rebate tiers as a staircase (rate to scale), purchases on x; markers sit on their step."""
    top_rate = max(t["rate"] for t in tiers)
    xmax = max(max(m[1] for m in markers) * 1.10, tiers[-1]["from"] * 1.3)
    padl, padr, axis_h, head = 8, 24, 40, 64
    pw = w - padl - padr
    base_y = h - axis_h
    ys = (base_y - head) / top_rate
    X = lambda v: padl + v / xmax * pw
    Y = lambda r: base_y - r * ys
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">']
    # the ladder: tinted steps with a data-blue top edge
    d_fill, d_edge = f"M{X(0):.1f} {base_y}", ""
    for t in tiers:
        x0, x1 = X(t["from"]), X(t["to"] if t["to"] is not None else xmax)
        d_fill += f"L{x0:.1f} {Y(t['rate']):.1f}L{x1:.1f} {Y(t['rate']):.1f}"
        d_edge += f"M{x0:.1f} {Y(t['rate']):.1f}H{x1:.1f}"
    d_fill += f"L{X(xmax):.1f} {base_y}Z"
    o.append(f'<path d="{d_fill}" fill="var(--data-blue)" fill-opacity=".10"/>')
    for t in tiers[1:]:
        o.append(f'<line class="keep-clear" x1="{X(t["from"]):.1f}" y1="{base_y}" x2="{X(t["from"]):.1f}" y2="{Y(t["rate"]):.1f}" stroke="var(--data-blue)" stroke-opacity=".35" stroke-width="1"/>')
    o.append(f'<path d="{d_edge}" fill="none" stroke="var(--data-blue)" stroke-width="2.5" stroke-linecap="round"/>')
    o.append(f'<line class="zero" x1="{padl}" y1="{base_y + .75}" x2="{X(xmax):.1f}" y2="{base_y + .75}"/>')
    for t in tiers:   # rate on each step, bound under each step start
        x0 = X(t["from"])
        o.append(f'<text class="c-value" x="{x0 + 14:.1f}" y="{Y(t["rate"]) - 22:.1f}" style="font-size:24px">{pct_keep(t["rate"])}</text>')
        o.append(f'<text class="c-axis" x="{x0:.1f}" y="{base_y + 24}" text-anchor="{"start" if t["from"] == 0 else "middle"}">{money_axis(t["from"])}</text>')
    for label, value, rate, em, dy in markers:
        x, y = X(value), Y(rate)
        step = next(t for t in tiers if t["from"] <= value and (t["to"] is None or value < t["to"]))
        lo, hi = X(step["from"]) + 12, X(step["to"] if step["to"] is not None else xmax) - 12
        tw = (M.width(label + " ", 20, "text", 500) + M.width(money(value), 20, "text", 600)) * 1.08
        cx = min(max(x, lo + tw / 2), hi - tw / 2)             # centred on the dot, but never across a riser
        o.append(f'<circle class="mark{" em" if em else ""}" cx="{x:.1f}" cy="{y:.1f}" r="8" stroke="#fff" stroke-width="2.5"/>')
        o.append(f'<text class="c-label" x="{cx:.1f}" y="{y + dy:.1f}" text-anchor="middle">{esc(label)} '
                 f'<tspan class="c-ref-v">{esc(money(value))}</tspan></text>')
    o.append("</svg>")
    return "".join(o)



def chart_timeline(M, items, as_of, w, h, labels):
    """S9: Feb 1 -> Aug 31 2026; points are deadlines at the end of a faint countdown track, ranges are bars."""
    d0 = dt.date(ymd(as_of).year, 2, 1)
    d1 = dt.date(ymd(as_of).year, 8, 31)
    span = (d1 - d0).days
    X = lambda d: (ymd(d) - d0).days / span * (w - 2) + 1 if isinstance(d, str) else (d - d0).days / span * (w - 2) + 1
    axis_y = h - 30
    head = 34
    lane = (axis_y - head - 10) / len(items)
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">',
         '<defs><linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--data-blue)" stop-opacity="1"/>'
         '<stop offset=".7" stop-color="var(--data-blue)" stop-opacity=".45"/><stop offset="1" stop-color="var(--data-blue)" stop-opacity=".08"/></linearGradient></defs>']
    # month ticks on a hairline axis
    o.append(f'<line class="zero" x1="0" y1="{axis_y + .75}" x2="{w}" y2="{axis_y + .75}"/>')
    for m in range(2, 9):
        xm = X(dt.date(d0.year, m, 1))
        o.append(f'<line x1="{xm:.1f}" y1="{axis_y - 5}" x2="{xm:.1f}" y2="{axis_y + 6}" stroke="var(--ink-3)" stroke-width="1"/>')
        o.append(f'<text class="c-axis" x="{xm + 6:.1f}" y="{axis_y + 20}">{MONTHS[m - 1]}</text>')
    xa = X(as_of)
    o.append(f'<line class="ref" x1="{xa:.1f}" y1="{head - 6}" x2="{xa:.1f}" y2="{axis_y}"/>')
    o.append(f'<text class="c-ref" x="{xa + 10:.1f}" y="{head / 2 - 4}">As of <tspan class="c-ref-v">{md(as_of)}</tspan></text>')
    for i, it in enumerate(items):
        top = head + 10 + lane * i
        ty = top + 14
        my = top + 46
        xs, xe = X(it["start"]), X(it["end"])
        lab = labels[it["id"]]
        tx = max(xs, xa + 12) if it["start"] != it["end"] else xa + 12
        o.append(f'<g><text class="c-label" x="{tx:.1f}" y="{ty:.1f}">{esc(smart(it["label"]))}'
                 f'<tspan class="c-ref-v" dx="16">{esc(lab[0])}</tspan><tspan class="c-sub" dx="12">{esc(lab[1])}</tspan></text>')
        if it["start"] == it["end"]:       # a deadline: faint countdown track from "as of", dot on the date
            o.append(f'<line x1="{xa:.1f}" y1="{my:.1f}" x2="{xe:.1f}" y2="{my:.1f}" stroke="var(--data-blue)" stroke-opacity=".35" stroke-width="2"/>')
            o.append(f'<circle class="mark" cx="{xe:.1f}" cy="{my:.1f}" r="9" stroke="#fff" stroke-width="2.5"/>')
        elif it.get("decay_per_day"):      # shrinking: the bar fades out towards its last day
            o.append(f'<rect class="keep-clear" x="{xs:.1f}" y="{my - 12:.1f}" width="{xe - xs:.1f}" height="24" rx="4" fill="url(#fade)"/>')
        else:
            o.append(f'<path class="mark" d="{rbar(xs, my - 12, xe - xs, 24)}"/>')
        o.append("</g>")
    o.append("</svg>")
    return "".join(o)


def chart_rcm(M, staff, star, w, h):
    """S10: claims worked (activity) and dollars recovered (output), same rows, sorted by dollars."""
    staff = sorted(staff, key=lambda p: -p["recovered"])
    head, n = 44, len(staff)
    pitch = (h - head) / n
    bar = min(22, pitch - 10)
    name_w = max(M.width(p["name"], 20, "text", 500) for p in staff) * 1.08
    tag_w = M.width("Denial queue", 16, "text", 500) + 40
    x_c = round(name_w + tag_w + 22)               # claims column
    col = (w - x_c - 60) / 2
    x_d = round(x_c + col + 60)                     # dollars column
    vw_c = M.width("2,578", 18, "display", 600) * 1.1 + 12
    vw_d = M.width("$291K", 18, "display", 600) * 1.1 + 12
    sc = (col - vw_c) / max(p["claims"] for p in staff)
    sd = (col - vw_d) / max(p["recovered"] for p in staff)
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">']
    o.append(f'<text class="c-ref" x="{x_c}" y="{head / 2 - 6}">Claims worked</text>')
    o.append(f'<text class="c-ref" x="{x_d}" y="{head / 2 - 6}">Dollars recovered</text>')
    o.append(f'<line class="zero" x1="{x_c - .75}" y1="{head - 8}" x2="{x_c - .75}" y2="{h}"/>')
    o.append(f'<line class="zero" x1="{x_d - .75}" y1="{head - 8}" x2="{x_d - .75}" y2="{h}"/>')
    for i, p in enumerate(staff):
        cy = head + pitch * (i + .5)
        y = round(cy - bar / 2)
        em = p["name"] == star
        cls = "mark em" if em else "mark"
        tag = ""
        if "queue" in p["title"].lower():
            tag = (f'<rect x="{name_w + 14:.1f}" y="{cy - 12:.1f}" width="{tag_w - 20:.1f}" height="24" rx="12" fill="none" stroke="var(--hairline)"/>'
                   f'<text class="c-sub" x="{name_w + 14 + (tag_w - 20) / 2:.1f}" y="{cy:.1f}" text-anchor="middle" style="font-size:15px;font-weight:500">Denial queue</text>')
        o.append(f'<g><title>{esc(p["name"])}, {esc(p["title"])}: {intc(p["claims"])} claims, {money(p["recovered"])}</title>'
                 f'<text class="c-label" x="0" y="{cy:.1f}" style="font-size:20px{";font-weight:600" if em else ""}">{esc(p["name"])}</text>{tag}'
                 f'<path class="{cls}" d="{rbar(x_c, y, p["claims"] * sc, bar)}"/>'
                 f'<text class="c-value" x="{x_c + p["claims"] * sc + 10:.1f}" y="{cy:.1f}" style="font-size:18px;fill:var(--ink-2)">{intc(p["claims"])}</text>'
                 f'<path class="{cls}" d="{rbar(x_d, y, p["recovered"] * sd, bar)}"/>'
                 f'<text class="c-value" x="{x_d + p["recovered"] * sd + 10:.1f}" y="{cy:.1f}" style="font-size:18px;fill:var(--ink-2)">{money(p["recovered"])}</text></g>')
    o.append("</svg>")
    return "".join(o)


def chart_gantt(M, mods, labels, w, h):
    """S12: plan.modules as bars on a week grid; a dot marks each module's go-live."""
    d0 = min(ymd(m["start"]) for m in mods)
    d1 = max(ymd(m["end"]) for m in mods)
    span = (d1 - d0).days
    X = lambda d: (d - d0).days / span * (w - 2) + 1
    axis_y, head = h - 30, 8
    lane = (axis_y - head - 12) / len(mods)
    o = [f'<svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">']
    wk = d0
    while wk <= d1:                                   # week ticks, month names on the first week of a month
        xw = X(wk)
        o.append(f'<line x1="{xw:.1f}" y1="{head}" x2="{xw:.1f}" y2="{axis_y}" stroke="var(--hairline)" stroke-width="1" stroke-opacity=".7"/>')
        if wk.day <= 7:
            o.append(f'<text class="c-axis" x="{xw + 6:.1f}" y="{axis_y + 18}">{MONTHS[wk.month - 1]} {wk.day}</text>')
        wk += dt.timedelta(days=7)
    o.append(f'<line class="zero" x1="0" y1="{axis_y + .75}" x2="{w}" y2="{axis_y + .75}"/>')
    for i, m in enumerate(mods):
        top = head + 12 + lane * i
        s_, e_ = ymd(m["start"]), ymd(m["end"])
        xs, xe = X(s_), X(e_ + dt.timedelta(days=1))
        by = round(top + 28)
        soft = m.get("software") is False
        o.append(f'<g><text class="c-label" x="{xs:.1f}" y="{top + 14:.1f}"><tspan class="c-ref-v">{m["n"]}</tspan>'
                 f'<tspan dx="10">{esc(smart(m["name"]))}</tspan></text>')
        fop = ' fill-opacity=".45"' if soft else ""
        o.append(f'<path class="mark" d="{rbar(xs, by, xe - xs, 22)}"{fop}/>')
        unl = labels[m["n"]]
        if m.get("live"):
            xl = X(ymd(m["live"]))
            o.append(f'<circle cx="{xl + 12:.1f}" cy="{by + 11}" r="6.5" fill="#fff" stroke="var(--data-blue)" stroke-width="2.5"/>')
            o.append(f'<text class="c-sub" x="{xl + 26:.1f}" y="{by + 11}">live {md(m["live"])}</text>')
        o.append(f'<text class="c-sub" x="{xs:.1f}" y="{by + 40}">{sdots(unl)}</text></g>')
    o.append("</svg>")
    return "".join(o)


# ---------------------------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------------------------
def all_sites(N):
    """Every site runs exactly one card processor, so the processors' site counts sum to the network."""
    return sum(p["sites"] for p in N("card_processing.processors"))


def s01(N, M):
    last = max(i["end"] for i in N("clocks.items"))
    meta = (f"Prepared for Dana Reyes, CFO · Ian Milkowski, Straterai · Data through {N('data_through_display')} · "
            f"As of {N('as_of_display')}")
    return slide(1, f"""
  {eyebrow("Northgate Dental Partners · FY2025 review")}
  <h1 class="cover-title t-cover">What Northgate<br>can recover</h1>
  <p class="cover-sub">{word(len(N('findings')), cap=True)} findings in Northgate’s FY2025 data, each traced to the rows behind it.</p>
  <div class="glass cover-slab">
    <div class="t-hero">{esc(N('totals.run_rate.display'))}</div>
    <p class="cover-line">a year, counted at the floor. Up to {esc(N('totals.run_rate_upper.display'))}.</p>
    <div class="cover-rule"></div>
    <p class="cover-once">+ <b>{esc(N('totals.one_time.display'))}</b> one-time, before {md(last)}</p>
  </div>
  <p class="source cover-meta">{sep().join(esc(x) for x in meta.split(' · '))}</p>""", "cover")


def s03(N, M):
    f, cc = fid(N, "charge_capture"), N("charge_capture")
    others = all_sites(N) - len(cc["sites"])                            # every site minus the flagged ones
    base1 = pct_keep(round(cc["baseline_pct"], 1))
    top, hgt = 382, 468
    chart = chart_sites(M, cc["sites"], cc["baseline_pct"], f"Other {others} sites", 1680 - 96, hgt - 68)
    q = cc["quote"]
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Unbilled procedures", f['basis'])}
  {headline(f['annual']['display'], "a year in procedures that were done but never billed")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:34px 48px">{chart}</div>
  <p class="under quote" style="top:{top + hgt + 30}px">“{esc(smart(q['text']))}.” <span class="who">{esc(q['who'])}, {esc(q['when'])}</span></p>
  {source(f"{f['source']} · above the {base1} baseline, at the {cc['net_collection_pct']}% collection rate")}""")



def s02(N, M):
    fs = N("findings")
    mx = max(f["upper"]["raw"] for f in fs)
    tw = max(M.width(smart(f["title"]), 24, "text", 400) for f in fs) * 1.10 + 32   # 8%+ slack and a gutter before the bars
    barw = int(1680 - 104 - 44 - tw - 150 - 170 - 176 - 36)   # what the fixed columns leave, less a gutter
    rows = []
    for f in fs:
        L = f["annual"]["raw"] / mx * (barw - 8)
        U = f["upper"]["raw"] / mx * (barw - 8)
        ext = (f'<path d="{rbar(0, 1, U, 22)}" fill="var(--data-blue)" fill-opacity=".22"/>' if U > L + 1 else "")
        svg = (f'<svg class="chart" width="{barw}" height="24" viewBox="0 0 {barw} 24"><title>{esc(f["title"])}: {esc(f["annual"]["display"])}</title>'
               f'{ext}<path class="mark" d="{rbar(0, 1, L, 22)}"/></svg>')
        rows.append(f'<tr><td class="rank">{f["rank"]}</td><td class="ttl">{esc(smart(f["title"]))}</td>'
                    f'<td>{svg}</td><td class="r num">{esc(f["annual"]["display"])}</td>'
                    f'<td class="r cash">{esc(f["upper"]["display"]) if f["upper"]["raw"] != f["annual"]["raw"] else "–"}</td><td class="r basis"><span class="tag">{esc(f["basis"])}</span></td></tr>')
    t = N("totals")
    stats = (f'<p>Closes <b>{t["pretax_gap_closed_pct"]}%</b> of the FY2025 pre-tax loss</p>'
             f'<p>One-time, with deadlines <b>{esc(t["one_time"]["display"])}</b></p>'
             f'<p>Not counted: <b>{esc(t["upside"]["display"])}</b> backfill upside, pilot first</p>')
    top, hgt = 262, 500
    cols = (f'<colgroup><col style="width:44px"><col style="width:{tw:.0f}px"><col><col style="width:150px">'
            f'<col style="width:170px"><col style="width:176px"></colgroup>')
    return slide(2, f"""
  {eyebrow("The answer")}
  <div class="titleblock"><h2 class="t-title">{esc(t['run_rate']['display'])} a year we can defend, up to {esc(t['run_rate_upper']['display'])}</h2></div>
  <div class="glass slab answer" style="top:{top}px; height:{hgt}px; padding:34px 52px 30px">
    <table class="tbl answer-t" style="table-layout:fixed">{cols}<thead><tr><th></th><th>Finding</th><th></th><th class="r key">Counted</th><th class="r">Up to</th><th class="r">Basis</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table>
  </div>
  <div class="stats" style="top:{top + hgt + 40}px">{stats}</div>
  {source("python -m northgate · findings.json")}""")


def s04(N, M):
    f, dp = fid(N, "denial_priority"), N("denial_priority")
    top, hgt = 382, 392
    fifo, vf = dp["writeoffs_fifo"]["raw"], dp["writeoffs_value_first"]["raw"]
    flat = dp["writeoffs_value_first_flat"]["raw"]   # value first, same work per claim: the upper bound
    chart = chart_pair(M, [("Written off today, oldest first", fifo, False),
                           ("Value first, bigger claims take more work", vf, True),
                           ("Value first, same work per claim", flat, False)],
                       1680 - 104, 250, money)
    ann = (f"{intc(dp['claims_lost'])} of {intc(dp['denials_total'])} denials age past the filing limit today. "
           f"The saving runs {dp['range_low']['display']} to {dp['range_high']['display']} a year, depending on how much more work a big claim takes.")
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Denial queue", f['basis'])}
  {headline(f['annual']['display'], "a year from working denials by value, counted at the cautious end")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:36px 52px">{chart}
    <p class="note" style="margin-top:22px">{esc(ann)}</p></div>
  <div class="under" style="top:{top + hgt + 34}px"><p class="note">The queue has no sort by dollars or days left (SOP 3.2–3.3). The first month of the ranked queue measures the real effort curve.</p></div>
  {source(f"{f['source']} · row-average claim values")}""")


def s05(N, M):
    f, dup = next(x for x in N("findings") if x["id"] == "duplicate_plans"), N("duplicate_plans")
    named = [n.lower() for n in dup["hr_named"]]
    rows = []
    for sl in dup["sellers"]:
        tag = '<span class="aside">named in HR’s email</span>' if any(sl["entity"].lower().startswith(n) for n in named) else ""
        rows.append(f'<tr><td>{esc(sl["entity"])}{tag}</td><td class="r soft">{sl["acquired"]}</td>'
                    f'<td class="r">{sl["people"]}</td><td class="r num">${intc(round(sl["annual"]))}</td></tr>')
    tot_people = sum(sl["people"] for sl in dup["sellers"])
    tot = sum(sl["annual"] for sl in dup["sellers"])
    rows.append(f'<tr class="total"><td>Total</td><td></td><td class="r">{tot_people}</td><td class="r num">${intc(round(tot))}</td></tr>')
    top, hgt = 382, 372
    callout = (f"HR’s August email names {word(len(dup['hr_named']))} sellers. "
               f"The carrier invoices show {word(len(dup['sellers']))}.")
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Duplicate health plans", f['basis'])}
  {headline(f['annual']['display'], f"a year for {dup['people']} employees still on a seller’s old plan as well as ours")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:34px 52px">
    <table class="tbl"><thead><tr><th>Seller</th><th class="r">Acquired</th><th class="r">People</th><th class="r">Per year</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
  <div class="under" style="top:{top + hgt + 34}px"><p class="callout">{esc(callout)}</p>
    <p class="note">Cancelling these plans is each seller’s obligation under the purchase agreement.</p></div>
  {source(f"{f['source']}")}""")


def s06(N, M):
    f, rb = next(x for x in N("findings") if x["id"] == "rebates"), N("rebates")
    markers = [("Schein 2025", rb["schein_2025"]["raw"], rb["current_rate_pct"], False, 34),
               ("Patterson 2025", rb["patterson_2025"]["raw"], rb["current_rate_pct"], False, 62),
               ("Combined", rb["combined_2025"]["raw"], rb["consolidated_rate_pct"], True, -30)]
    top, hgt = 382, 372
    chart = chart_ladder(M, rb["tiers"], markers, 1680 - 104, hgt - 64)
    lo, hi = rb["schein_share_range_pct"]
    stats = (f'<p>Rebate income in the FY2025 P&amp;L and AP ledger: <b>{esc(rb["collected"]["display"])}</b></p>'
             f'<p>Schein share of purchase orders, every month: <b>{pct_keep(lo)[:-1]}–{pct_keep(hi)}</b></p>')
    note = ("Counted at the floor: Patterson’s terms don’t say whether the rate covers the whole amount, and Schein pools only the sites on "
            f"its Schedule A. For 2026, move volume to {rb['recommend_2026']} from March ({rb['fy2026']['display']} to {rb['fy2026_upper']['display']}), "
            "compare item prices first, and rebid both at renewal.")
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Supply rebates", f['basis'])}
  {headline(f['annual']['display'], f"a year at the floor, up to {rb['upper']['display']}, from one distributor and every claim filed")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:32px 52px">{chart}</div>
  <div class="stats" style="top:{top + hgt + 34}px">{stats}</div>
  <div class="under" style="top:{top + hgt + 88}px; max-width:1560px"><p class="note">{esc(note)}</p></div>
  {source(f"{f['source']} · Schein agreement §7.2–7.3")}""")


def s07(N, M):
    f, gs = fid(N, "ghost_spend"), N("ghost_spend")
    sites = sum(1 for r in gs["rows"] if r["label"].startswith("NGD-"))
    rows = [f'<tr><td class="lbl">{dots(r["label"])}</td><td class="soft">{esc(r["detail"])}</td><td class="r num">${intc(round(r["annual"]))}</td></tr>'
            for r in gs["rows"]]
    rows.append(f'<tr class="total"><td>Total</td><td></td><td class="r num">${intc(round(sum(r["annual"] for r in gs["rows"])))}</td></tr>')
    N.gap("ghost_spend: count of scanned invoices (spec source line says “3 scanned invoices”)")
    top, hgt = 382, 318
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Spend with no practice behind it", f['basis'])}
  {headline(f['annual']['display'], f"a year for {word(sites)} sites with no patients or staff, and ads in a city with no practice")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:34px 52px">
    <table class="tbl ghost"><thead><tr><th>Cost</th><th>What it pays for</th><th class="r">Per year</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
  <div class="under" style="top:{top + hgt + 34}px"><p class="note">{esc(smart(gs['evidence_note']))}</p>
    <p class="note">Halstead {esc(smart(gs['halstead_fy2026_note'][0].lower() + gs['halstead_fy2026_note'][1:]))}</p></div>
  {source(f"{f['source']} · scanned invoices")}""")


def s08(N, M):
    f, cp = fid(N, "card_processing"), N("card_processing")
    procs = cp["processors"]
    total_sites = all_sites(N)
    moving = total_sites - cp["sunbit_processing_sites"]
    low = min(procs, key=lambda p: p["rate_pct"])
    rows = [(f"{p['name']} · {p['sites']} sites · {money(p['volume'])}", p["rate_pct"], p is low) for p in procs]
    top, hgt = 382, 356
    chart = chart_pair(M, rows, 1680 - 104, hgt - 72, pct_keep)
    callout = (f"All {cp['sunbit_fee_sites']} sites already pay Sunbit’s platform fee. "
               f"Only {cp['sunbit_processing_sites']} process through it.")
    return slide(2 + f["rank"], f"""
  {eyebrow(f"{f['rank']} · Card processing", f['basis'])}
  {headline(f['annual']['display'], f"a year by moving {moving} sites to the rate {cp['sunbit_processing_sites']} sites already get")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:36px 52px">{chart}</div>
  <div class="under" style="top:{top + hgt + 34}px"><p class="callout">{esc(callout)}</p>
    <p class="note">Exit terms for BluePay and CardConnect aren’t in the packet; confirm them first.</p></div>
  {source(f"{f['source']}")}""")


def s09(N, M):
    ck = N("clocks")
    items = sorted(ck["items"], key=lambda i: (i["start"], i["end"]))
    labels = {}
    for it in ck["items"]:
        amt = it["amount"]["display"] + (f"–{it['amount_high']['display']}" if it.get("amount_high") else "")
        if it["amount"].get("raw") is None:
            labels[it["id"]] = (amt, "overdue now")
        elif it["id"] == "credential_hold":
            labels[it["id"]] = (amt, f"claims expire {md(it['start'])} → {md(it['end'])}")
        elif it["start"] == it["end"]:
            labels[it["id"]] = (amt, f"by {md(it['end'])}")
        elif it.get("decay_per_day"):
            per_day = f"${intc(rhu(it['decay_per_day'], -2))}"
            labels[it["id"]] = (amt, f"{md(it['start'])} → {md(it['end'])}, shrinking about {per_day} a day")
        else:
            labels[it["id"]] = (amt, f"{md(it['start'])} → {md(it['end'])}")
    top, hgt = 382, 470
    chart = chart_timeline(M, items, N("as_of"), 1680 - 104, hgt - 64, labels)
    return slide(9, f"""
  {eyebrow("Time-sensitive")}
  {headline(ck['total']['display'], "one-time, if we act before each deadline")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:32px 52px">{chart}</div>
  {source("claim-denials.csv · provider-roster.csv · procedures-monthly.csv · both supply agreements")}""")


def s10(N, M):
    pp = N("people")
    mg = pp["marguerite"]
    star = next(p["name"] for p in pp["rcm"] if abs(p["recovered"] - mg["recovered"]["raw"]) < 1)
    q = pp["queue_per_claim"]
    qtxt = f"${min(q)}" if min(q) == max(q) else f"${min(q)}–{max(q)}"
    top, hgt = 322, 590
    chart = chart_rcm(M, pp["rcm"], star, 1128 - 96, hgt - 60)
    return slide(10, f"""
  {eyebrow("Before anyone reads the dashboards")}
  <div class="titleblock"><h2 class="t-title">The easiest cut on the dashboard<br>is your best recoverer</h2></div>
  <div class="glass slab" style="top:{top}px; width:1128px; height:{hgt}px; padding:30px 48px">{chart}</div>
  <div class="side" style="top:{top + 8}px">
    <div class="st"><p class="big"><b>{esc(mg['recovered']['display'])}</b> recovered · <b>${mg['per_claim']}</b> per claim worked</p>
      <p class="small">(team median about ${pp['team_median_per_claim']}; queue specialists <span class="nb">{qtxt}</span>)</p></div>
    <div class="st"><p class="big"><b>{mg['onsite_hrs_mo']}</b> on-site hours a month, lowest of {mg['fulltime_staff']} full-time staff.</p>
      <p class="small">She works aged claims by phone.</p></div>
    <div class="st"><p class="small" style="margin:0">Hired {mg['hired']}. Keeps the payer contact list. <span style="color:var(--ink)">The risk is losing her.</span></p></div>
  </div>
  {source("denial-worklog.csv · network-activity.csv · employees.csv")}""")


def s11(N, M):
    pp, cc = N("people"), N("charge_capture")
    titles = [p["title"] for p in pp["rcm"]]
    n_queue = sum(1 for t in titles if t == "Denial Queue Specialist")
    n_senior = sum(1 for t in titles if t == "Senior AR Specialist")
    rows = [
        (f"Billing Entry Clerks <span class=\"n\">({pp['clerks']})</span>",
         f"Key paper routing slips from {len(cc['sites'])} sites, and work about {intc(pp['clerk_denials_per_year'])} denials each a year",
         "Finding what the slips missed: a daily list of procedures done but not billed", "Keying those first, then the backlog. Their denial work stays"),
        (f"Denial Queue Specialists <span class=\"n\">({n_queue})</span>", "Rework denials oldest first", "The ordering",
         "The ranked queue: highest value, nearest deadline first"),
        (f"Senior AR Specialist <span class=\"n\">({n_senior})</span>", "Aged claims, by phone", "Nothing. It hands her the largest aged claims",
         "Same work. One Revenue Cycle Specialist shadows her a day a week"),
        (f"Front desk, Worthington and Dublin <span class=\"n\">({pp['eligibility_staff']})</span>",
         f"{pp['eligibility_minutes_per_patient']} minutes a patient on payer portals",
         "Eligibility checks through DentalXChange, already paid for", "Filling same-day openings from the waitlist"),
    ]
    body = "".join(f'<tr><td class="role">{a}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>' for a, b, c, d in rows)
    N.gap("corporate headcount (spec footer: “Corporate headcount stays at 31”)")
    top, hgt = 262, 486
    return slide(11, f"""
  {eyebrow("Where the work goes")}
  <div class="titleblock"><h2 class="t-title">Nobody is cut. The work moves.</h2></div>
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:34px 52px">
    <table class="tbl work" style="table-layout:fixed"><colgroup><col style="width:22%"><col style="width:23%"><col style="width:27%"><col style="width:28%"></colgroup>
    <thead><tr><th>Role</th><th>Today</th><th>The system takes</th><th>They move to</th></tr></thead><tbody>{body}</tbody></table></div>
  <div class="under" style="top:{top + hgt + 36}px"><p class="callout">What stays with people: payer calls, appeals, coding judgment. No new hires; the freeze holds.</p></div>""")


UNLOCK_LABELS = {  # short names for what each module unlocks (copy; ids come from plan.modules[].unlocks)
    "charge_capture": "Unbilled procedures", "backlog": "Filing-limit backlog", "denial_priority": "Denial queue",
    "credential_hold": "Dr. Osei’s held claims", "duplicate_plans": "Duplicate plans", "rebates": "Rebates",
    "ghost_spend": "Spend with no practice", "card_processing": "Card processing", "backfill": "Same-day openings, pilot first",
}


def s12(N, M):
    pl, t = N("plan"), N("totals")
    mods = pl["modules"]
    n_soft = sum(1 for m in mods if m.get("software") is not False)
    labels = {m["n"]: " · ".join(UNLOCK_LABELS.get(u, u) for u in m.get("unlocks", [])) or "The time-sensitive items" for m in mods}
    top, hgt = 322, 600
    chart = chart_gantt(M, mods, labels, 1128 - 96, hgt - 60)
    live_last = max(m["live"] for m in mods if m.get("live"))
    live_last = __import__("datetime").date.fromisoformat(live_last).strftime("%B %-d")
    stats = [f'<p class="big"><b>{esc(t["build_cost"]["display"])}</b> to build</p><p class="small">Estimate: {pl["engineers"]} engineers for {pl["weeks"]} weeks</p>',
             f'<p class="big"><b>{money(t["run_cost_monthly"]["raw"], sentence=True)}</b> a month to run</p>',
             f'<p class="big">One-time recoveries alone cover the build <b>{t["one_time_covers_build"]}×</b></p>',
             f'<p class="big"><b>{esc(t["fy2026_total"]["display"])}</b> in 2026</p><p class="small">{esc(t["fy2026_net"]["display"])} after the build and running costs</p>']
    side = "".join(f'<div class="st">{x}</div>' for x in stats)
    return slide(12, f"""
  {eyebrow("What we’d build")}
  <div class="titleblock"><h2 class="t-title">{word(n_soft, cap=True)} pieces, in this order.<br>Three are live by {live_last}.</h2></div>
  <div class="glass slab" style="top:{top}px; width:1128px; height:{hgt}px; padding:30px 48px">{chart}</div>
  <div class="side" style="top:{top + 8}px">{side}</div>
  {source("python -m northgate · plan")}""")


def s13(N, M):
    items = N("not_proposing")
    half = (len(items) + 1) // 2
    order = [items[i // 2 + (half if i % 2 else 0)] for i in range(len(items))]   # column-major in a 2-column grid
    cells = "".join(f'<div class="it"><h3>{esc(smart(x["item"]))}</h3><p>{esc(smart(x["reason"]))}</p></div>' for x in order)
    top, hgt = 262, 598
    return slide(13, f"""
  {eyebrow("What we’re not proposing")}
  <div class="titleblock"><h2 class="t-title">Things that look like savings and aren’t</h2></div>
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:36px 52px"><div class="list">{cells}</div></div>
  {source("Legal memo Sep 4, 2024 · appendix §2–3, §5, §8 · CFO email Oct 1, 2025")}""")


def s14(N, M):
    bf, pl = N("backfill"), N("plan")
    N.gap("backfill: site counts for the two groups (spec: “6 sites acquired since 2024”, “16 earlier sites”)")
    N.gap("backfill: row count of operations-monthly.csv (spec source: “264 rows”)")
    pilot = next((m for m in pl["modules"] if "backfill" in m.get("unlocks", [])), None)
    mt = re.search(r"(\d+)\s+sites\s+for\s+(\d+)\s+days", pilot["what"]) if pilot else None
    if not mt:
        N.gap("plan: pilot site count and length (parsed from plan.modules[].what)")
    pilot_txt = f"Pilot: {mt.group(1)} sites, {mt.group(2)} days." if mt else "Pilot first."
    top, hgt = 382, 356
    bars = chart_pair(M, [("Sites acquired since 2024", bf["recent_rate_pct"], True),
                          ("Earlier sites", bf["legacy_rate_pct"], False)], 1680 - 104, 176, pct_keep)
    op = lambda x: f'<span class="op">{x}</span>'
    chain = (f'<b>{intc(bf["openings"])}</b> openings {op("×")} <b>{bf["fill_pct"]}%</b> filled {op("×")} <b>${bf["per_visit"]}</b> a visit '
             f'{op("×")} <b>{bf["collection_pct"]}%</b> collected {op("×")} <b>{bf["margin_pct"]}%</b> margin {op("=")} <b>{esc(bf["contribution"]["display"])}</b>')
    return slide(14, f"""
  {eyebrow("Upside we’re not counting yet")}
  {headline(bf['contribution']['display'], "a year from filling same-day openings, if a pilot proves it")}
  <div class="glass slab" style="top:{top}px; height:{hgt}px; padding:32px 52px">
    <p class="c-cap t-small" style="margin:0 0 6px">Same-day openings rate</p>{bars}
    <div style="height:1px;background:var(--hairline);margin:18px 0 22px"></div><p class="chain">{chain}</p></div>
  <div class="under" style="top:{top + hgt + 34}px"><p class="note">Fill rate has never been measured, and some filled slots only pull future visits forward. If managers already fill 20% of openings, the gain is about {esc(bf['incremental_if_20pct']['display'])}. {esc(pilot_txt)}</p></div>
  {source("operations-monthly.csv · appendix §6")}""")


def s15(N, M):
    me, dv, tz = N("method"), N("docs_vs_data"), N("tieouts_summary")
    short = {"Denied $: claims-monthly vs claim-denials": "denied dollars between the two billing files",
             "NGD-23/24 software: ap-ledger vs vendor-spend": "NGD-23/24 software missing from vendor spend",
             "Corporate payroll: employees x 1.21 vs P&L": "corporate payroll"}
    tz_big = "; ".join(f"{short.get(b['label'], b['label'])} {b['diff']['display']}" for b in tz["largest"])
    rows = "".join(f'<tr><td class="who">{esc(r["who"])}</td><td>{esc(smart(r["claim"]))}</td><td>{esc(smart(r["data"]))}</td></tr>' for r in dv)
    top = 346
    return slide(15, f"""
  {eyebrow("How we know")}
  <div class="titleblock"><h2 class="t-title">{intc(me['packet_words'])} words, {me['signal_documents']} documents that mattered, one command</h2></div>
  <div class="glass slab flow" style="top:{top}px; width:576px; height:486px; padding:38px 44px">
    <p class="stat"><span class="v">{intc(me['corpus_words'])}</span><span class="d">words of meetings, email and chat</span></p>
    <div class="arrow">↓</div>
    <p class="stat"><span class="v">{intc(me['rare_words'])}</span><span class="d">words that weren’t boilerplate ({me['reduction_pct']}% removed)</span></p>
    <div class="arrow">↓</div>
    <p class="stat"><span class="v">{me['signal_documents']}</span><span class="d">documents read in full; a second pass checked everything dropped</span></p>
  </div>
  <div class="dvd" style="top:{top}px"><h3>Where the documents disagree with the data</h3>
    <table class="tbl dvd-t" style="table-layout:fixed"><colgroup><col style="width:23%"><col style="width:36%"><col style="width:41%"></colgroup>
    <thead><tr><th>Who</th><th>Claim</th><th>Data</th></tr></thead><tbody>{rows}</tbody></table>
    <p class="note" style="margin-top:14px">P&amp;L tie-outs: {tz['breaks']} breaks in {tz['checks']} checks, the largest {esc(tz['largest'][0]['diff']['display'])} between the two billing files.</p></div>
  <div class="cmd" style="top:{top + 486 + 84}px"><span class="lbl">Reproduce any number:</span><div class="glass glass--capsule">python -m northgate explain &lt;finding&gt;</div></div>""")


FINDING_SLIDES = {"charge_capture": s03, "denial_priority": s04, "duplicate_plans": s05,
                  "rebates": s06, "ghost_spend": s07, "card_processing": s08}


def slide_order(N):
    """Finding slides follow the system's ranks; everything else is fixed."""
    order = {1: s01, 2: s02, 9: s09, 10: s10, 11: s11, 12: s12, 13: s13, 14: s14, 15: s15}
    for f in N("findings"):
        order[2 + f["rank"]] = FINDING_SLIDES[f["id"]]
    return order


SLIDES = {1: s01, 2: s02, 3: s03, 4: s04, 5: s06, 6: s05, 7: s07, 8: s08,
          9: s09, 10: s10, 11: s11, 12: s12, 13: s13, 14: s14, 15: s15}


# ---------------------------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------------------------
def write_deck(N, M, fonts, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    kit = OUT / "kit"
    (kit / "fonts").mkdir(parents=True, exist_ok=True)
    for f in ("glass.css", "glass.js"):
        shutil.copy2(KIT / f, kit / f)
    for f in (KIT / "fonts").glob("InstrumentSans*"):
        shutil.copy2(f, kit / "fonts" / f.name)
    (OUT / "deck.css").write_text(DECK_CSS.lstrip())
    order = slide_order(N)
    nums = [n for n in sorted(order) if not only or n in only]
    body = "\n".join(order[n](N, M) for n in nums)
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Northgate: what’s recoverable</title>
<link rel="stylesheet" href="kit/glass.css">
<style>
{font_css(fonts)}</style>
<link rel="stylesheet" href="deck.css">
</head>
<body>
{body}
<script src="kit/glass.js"></script>
</body>
</html>
"""
    path = OUT / "deck.html"
    path.write_text(doc)
    return path, nums


# ---------------------------------------------------------------------------------------------
# checks: collisions, clipping, 8% slack, chrome in the same place on every slide
# ---------------------------------------------------------------------------------------------
CHECK_JS = r"""
() => {
  const issues = [], chrome = [];
  const inter = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
                          Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  const shrink = (r, f) => { const d = r.height * f; return {left: r.left + .5, right: r.right - .5, top: r.top + d, bottom: r.bottom - d, width: r.width, height: r.height - 2 * d}; };
  document.querySelectorAll('section.slide').forEach(s => {
    const n = +s.dataset.n, sr = s.getBoundingClientRect(), items = [];
    const walker = document.createTreeWalker(s, NodeFilter.SHOW_TEXT);
    let t;
    while ((t = walker.nextNode())) {
      if (!t.textContent.trim()) continue;
      const el = t.parentElement;
      if (el.closest('.glass__backdrop, .glass__rim, title, defs')) continue;
      if (el.closest('svg')) continue;                       // SVG text handled below
      const rg = document.createRange(); rg.selectNodeContents(t);
      for (const b of rg.getClientRects()) if (b.width > .5) items.push({kind: 'text', el, node: t, b: shrink(b, .14), raw: b, txt: t.textContent.trim().slice(0, 48)});
    }
    s.querySelectorAll('svg text').forEach(el => { if (el.closest('defs, title')) return;
      const b = el.getBoundingClientRect(); if (b.width > .5) items.push({kind: 'text', el, node: el, b: shrink(b, .14), raw: b, txt: el.textContent.trim().slice(0, 48)}); });
    s.querySelectorAll('.mark, .ref, .keep-clear').forEach(el => { const b = el.getBoundingClientRect(); items.push({kind: 'mark', el, node: el, b, raw: b, txt: el.getAttribute('class')}); });
    // clipping: inside the slide's safe box, and inside the glass that holds it
    items.filter(i => i.kind === 'text').forEach(i => {
      const b = i.raw;
      if (b.left < sr.left + 40 || b.right > sr.right - 40 || b.top < sr.top + 40 || b.bottom > sr.bottom - 40)
        issues.push({slide: n, type: 'near-edge', text: i.txt});
      const g = i.el.closest('.glass');
      if (g) { const gb = g.getBoundingClientRect();
        if (b.left < gb.left + 12 || b.right > gb.right - 12 || b.top < gb.top + 6 || b.bottom > gb.bottom - 6)
          issues.push({slide: n, type: 'outside-glass', text: i.txt, over: Math.round(Math.max(gb.left + 12 - b.left, b.right - gb.right + 12, gb.top + 6 - b.top, b.bottom - gb.bottom + 6))}); }
    });
    // overlaps: text/text from different nodes, text/mark unless the text is meant to sit on the mark
    for (let a = 0; a < items.length; a++) for (let c = a + 1; c < items.length; c++) {
      const A = items[a], C = items[c];
      if (A.kind === 'mark' && C.kind === 'mark') continue;
      if (A.node === C.node || A.el.contains(C.el) && A.kind === 'mark' || C.el.contains(A.el) && C.kind === 'mark') continue;
      if ((A.kind === 'mark' && C.el.closest('.on-mark')) || (C.kind === 'mark' && A.el.closest('.on-mark'))) continue;
      const ov = inter(A.b, C.b);
      if (ov > 4) issues.push({slide: n, type: 'overlap', a: A.txt, b: C.txt, px: Math.round(ov)});
    }
    // elements that must stay on one line
    s.querySelectorAll('.t-hero, .source, .eyebrow, .nowrap').forEach(el => { if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible')
      issues.push({slide: n, type: 'overflow', text: el.textContent.trim().slice(0, 48)}); });
    const box = sel => { const e = s.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect();
      return [Math.round(b.left - sr.left), Math.round(b.top - sr.top), Math.round(b.bottom - sr.top)]; };
    chrome.push({slide: n, eyebrow: box('.eyebrow'), source: box('.source'), pill: box('.page-pill')});
  });
  return {issues, chrome};
}
"""


def run_checks(page, log=print):
    res = page.evaluate(CHECK_JS)
    page.evaluate("document.documentElement.style.setProperty('--slack', '.04em')")
    page.wait_for_timeout(120)
    slack = page.evaluate(CHECK_JS)
    page.evaluate("document.documentElement.style.removeProperty('--slack')")
    page.wait_for_timeout(60)
    issues = res["issues"] + [dict(i, slack=True) for i in slack["issues"] if i not in res["issues"]]
    # chrome consistency (eyebrow top-left, source bottom-left, pill bottom-right)
    ch = res["chrome"]
    for key, idx in (("eyebrow", (0, 1)), ("source", (0, 2)), ("pill", (0, 1))):
        vals = {tuple(c[key][j] for j in idx) for c in ch if c[key]}
        if len(vals) > 1:
            issues.append({"type": "chrome-moves", "what": key, "positions": sorted(vals)})
    return issues


# ---------------------------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------------------------
def load_kit_render():
    spec = importlib.util.spec_from_file_location("kit_render", KIT / "render.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def screens_and_checks(deck, dest, nums, dpr=1, shots=True, log=print):
    from playwright.sync_api import sync_playwright
    dest.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=dpr)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(deck.as_uri())
        pg.wait_for_function("window.__glassReady === true", timeout=60000)
        pg.wait_for_timeout(150)
        issues = run_checks(pg, log)
        loaded = pg.evaluate("[...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight))]")
        if shots:
            s = pg.locator("section.slide")
            for i, n in enumerate(nums):
                s.nth(i).screenshot(path=str(dest / f"slide-{n:02d}@{dpr}x.png"))
        b.close()
    return issues + [{"type": "page-error", "text": e} for e in errs], loaded


def contact_sheet(pngs, dest):
    from PIL import Image, ImageDraw, ImageFont
    cols, tw, th, gap, pad = 3, 600, 338, 28, 56
    rows = (len(pngs) + cols - 1) // cols
    sheet = Image.new("RGB", (pad * 2 + cols * tw + (cols - 1) * gap, pad * 2 + rows * (th + 34) + (rows - 1) * gap - 10), (226, 232, 241))
    d = ImageDraw.Draw(sheet)
    try:
        fnt = ImageFont.truetype(str(KIT / "fonts" / "InstrumentSans-Medium.ttf"), 17)
    except Exception:
        fnt = ImageFont.load_default()
    for k, p in enumerate(pngs):
        im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        x = pad + (k % cols) * (tw + gap)
        y = pad + (k // cols) * (th + 34 + gap)
        sheet.paste(im, (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + th], outline=(203, 213, 227))
        num = int(re.search(r"(\d+)@", p.name).group(1))
        d.text((x, y + th + 9), f"{num:02d}", font=fnt, fill=(91, 100, 117))
    sheet.save(dest)
    return dest


# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numbers", default="auto", help="auto (real if ready, else example) | real | example | <path>")
    ap.add_argument("--wait", type=int, default=0, help="seconds to wait for the real numbers file")
    ap.add_argument("--slides", default="", help="subset, e.g. 1,3")
    ap.add_argument("--quick", action="store_true", help="screens + checks only (no PDF)")
    args = ap.parse_args()
    only = {int(x) for x in args.slides.split(",") if x.strip()} or None

    N = load_numbers(args.numbers, args.wait)
    fonts = discover_fonts()
    M = Metrics(fonts)
    deck, nums = write_deck(N, M, fonts, only)
    print(f"numbers: {N.path}\nfonts:   {fonts['source']}\ndeck:    {deck}  ({len(nums)} slides)")

    issues, loaded = screens_and_checks(deck, OUT / "quick", nums, shots=args.quick)
    print("loaded:  " + ", ".join(loaded))
    for i in issues:
        print("  check:", json.dumps(i, ensure_ascii=False))
    print(f"checks:  {len(issues)} issue(s)")
    if args.quick:
        return
    kit = load_kit_render()
    rep = kit.render(deck, OUT / "render", bake="all", plate="jpg", pdf_name="Northgate-Recoverable.pdf", scales=(1,))
    pdf = OUT / "Northgate-Recoverable.pdf"
    shutil.copy2(OUT / "render" / "Northgate-Recoverable.pdf", pdf)
    (OUT / "png").mkdir(exist_ok=True)
    for f in (OUT / "png").glob("*.png"):
        f.unlink()
    pngs = []
    for i, n in enumerate(nums):
        dst = OUT / "png" / f"slide-{n:02d}@1x.png"
        shutil.copy2(OUT / "render" / "screen" / f"slide-{i + 1:02d}@1x.png", dst)
        pngs.append(dst)
    contact_sheet(pngs, OUT / "contact-sheet.png")
    missing = N.missing
    summary = {"numbers": str(N.path), "fonts": fonts["source"], "pdf": str(pdf), "pdf_mb": round(pdf.stat().st_size / 1e6, 2),
               "slides": nums, "check_issues": issues, "missing_keys": missing,
               "text_missing_in_pdf": {r["slide"]: r["text"]["missing"] for r in rep["slides"] if r["text"]["missing"]},
               "plate_check": rep.get("plate_check")}
    (OUT / "build-report.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"pdf:     {pdf} ({summary['pdf_mb']} MB)   plates: {rep.get('plate_check')}")
    print(f"sheet:   {OUT / 'contact-sheet.png'}")
    print("missing keys: " + (", ".join(missing) if missing else "none"))


if __name__ == "__main__":
    main()
