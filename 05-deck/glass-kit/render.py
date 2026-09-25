#!/usr/bin/env python3
"""Render glass-kit slides: screen PNGs, a PDF, the PDF rasterised back to PNG,
and a fidelity report (screen vs PDF, text extractability, what got rasterised).

    python3 render.py                      # test.html -> renders/
    python3 render.py lab.html --out renders/lab --bake marked
    python3 render.py --bake none          # technique (c) alone: live filters in the PDF

Export technique (default --bake all): each slide's field + glass material is
screenshotted at 2x with every piece of ink hidden (the "plate"), the plate
becomes that slide's background, the material layers are removed, and
Chromium prints the live text and SVG chart on top. Text stays vector and
selectable; the glass is pixel-identical to the screen render.

Requires: Python playwright (Chromium from PLAYWRIGHT_BROWSERS_PATH, default
/opt/pw-browsers), Pillow, numpy, poppler-utils (pdftoppm/pdftotext/pdffonts/
pdfimages; falls back to PyMuPDF for rasterising if pdftoppm is missing).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

KIT = Path(__file__).resolve().parent
W, H = 1920, 1080
FONT_FILES = {  # Fontsource file -> package
    "inter-latin-400-normal.woff2": "@fontsource/inter",
    "inter-latin-500-normal.woff2": "@fontsource/inter",
    "inter-latin-600-normal.woff2": "@fontsource/inter",
    "inter-tight-latin-500-normal.woff2": "@fontsource/inter-tight",
    "inter-tight-latin-600-normal.woff2": "@fontsource/inter-tight",
}


def ensure_fonts(fonts: Path) -> bool:
    """Copy Inter / Inter Tight woff2 files into fonts/ (npm, once). Returns True if present."""
    missing = [f for f in FONT_FILES if not (fonts / f).exists()]
    if not missing:
        return True
    if not shutil.which("npm"):
        print("fonts: npm not found; using the stand-in font")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        pkgs = sorted({FONT_FILES[f] for f in missing})
        r = subprocess.run(["npm", "install", "--no-save", "--no-audit", "--no-fund", "--prefix", tmp, *pkgs],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            last = (r.stderr.strip().splitlines() or ["?"])[-1]
            print(f"fonts: npm install failed ({last}); using the stand-in font")
            return False
        for f in missing:
            src = Path(tmp) / "node_modules" / FONT_FILES[f] / "files" / f
            if src.exists():
                shutil.copy2(src, fonts / f)
    ok = all((fonts / f).exists() for f in FONT_FILES)
    print("fonts: Inter + Inter Tight installed into fonts/" if ok else "fonts: some files missing; stand-in used where needed")
    return ok


def wait_ready(page):
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=30000)
    has_kit = page.evaluate("!!document.querySelector('script[src$=\"glass.js\"]')")
    if has_kit:
        page.wait_for_function("window.__glassReady === true", timeout=30000)
    page.wait_for_timeout(150)


def slide_count(page):
    return page.locator("section.slide").count()


def rasterise(pdf: Path, dpi: int, prefix: Path):
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(prefix)], check=True)
        pages = sorted(prefix.parent.glob(prefix.name + "-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
        return pages
    import fitz  # PyMuPDF fallback: pip install pymupdf --break-system-packages
    out = []
    for i, pg in enumerate(fitz.open(pdf)):
        p = prefix.parent / f"{prefix.name}-{i + 1}.png"
        pg.get_pixmap(dpi=dpi).save(p)
        out.append(p)
    return out


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def diff_stats(a, b, mask=None):
    d = np.abs(a - b).max(axis=2)
    sel = d if mask is None else d[mask]
    if sel.size == 0:
        return None, d
    return {"mae": round(float(sel.mean()), 3), "p99": int(np.percentile(sel, 99)),
            "max": int(sel.max()), "gt8": round(float((sel > 8).mean()) * 100, 3)}, d


def words(s):
    return [w for w in re.split(r"[\s\u00b7]+", s) if w]


def render(html, out, bake="all", plate="png", pdf_name=None, scales=(1, 2), fetch_fonts=False, log=print):
    """Screens at each scale in `scales`, 2x plates, baked PDF, rasterised PDF, fidelity report. Returns the report."""
    html, out = Path(html).resolve(), Path(out).resolve()
    for sub in ("screen", "pdf", "plates", "diff"):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for f in (out / sub).glob("*"):
            f.unlink()
    pdf_path = out / (pdf_name or (html.stem + ".pdf"))
    if fetch_fonts:
        ensure_fonts(KIT / "fonts")

    report = {"html": str(html), "bake": bake, "plate": plate, "slides": []}
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for dpr in (1, 2):
            ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=dpr)
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(html.as_uri())
            wait_ready(page)
            n = slide_count(page)
            slides = page.locator("section.slide")
            # 1. live screen renders
            if dpr in scales:
                for i in range(n):
                    slides.nth(i).screenshot(path=str(out / "screen" / f"slide-{i + 1:02d}@{dpr}x.png"))
            if dpr == 1:
                report["fonts_loaded"] = page.evaluate(
                    "[...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight))]")
                report["dom_text"] = page.evaluate(
                    "[...document.querySelectorAll('section.slide')].map(s => s.innerText)")
                report["glass_rects"] = page.evaluate("""[...document.querySelectorAll('section.slide')].map(s => {
                    const r0 = s.getBoundingClientRect();
                    return [...s.querySelectorAll('.glass')].map(g => { const r = g.getBoundingClientRect();
                      return [r.left - r0.left, r.top - r0.top, r.width, r.height].map(Math.round); }); })""")
                if errors:
                    report["page_errors"] = errors
                ctx.close()
                continue

            # 2. plates (material only, 2x) for every slide: used for baking and as the ink mask
            baked = []
            for i in range(n):
                el = slides.nth(i)
                el.evaluate("s => s.classList.add('kit-plate')")
                plate_png = out / "plates" / f"slide-{i + 1:02d}.png"
                el.screenshot(path=str(plate_png))
                el.evaluate("s => s.classList.remove('kit-plate')")
                mark = el.evaluate("s => s.hasAttribute('data-bake')")
                if bake == "all" or (bake == "marked" and mark):
                    src = plate_png
                    if plate == "jpg":
                        src = plate_png.with_suffix(".jpg")
                        Image.open(plate_png).convert("RGB").save(src, quality=92, subsampling=0, optimize=True)
                    # an <img>, not a CSS background: it can be awaited (decode) before printing
                    ok = el.evaluate("""async (s, url) => {
                        const img = new Image(); img.className = 'kit-plate-img'; img.alt = '';
                        img.src = url; await img.decode();
                        s.prepend(img); s.classList.add('kit-baked');
                        return img.naturalWidth; }""", src.as_uri())
                    if ok != 2 * W:
                        raise RuntimeError(f"plate for slide {i + 1} did not load ({ok}px)")
                    baked.append(i)
            # every plate was decoded and size-checked when it went in; here only confirm they are all still complete
            # (a blanket decode() of many 3840px images can fail under memory pressure, and printing decodes anyway)
            bad = page.evaluate("[...document.querySelectorAll('img.kit-plate-img')].filter(i => !i.complete || i.naturalWidth !== %d).length" % (2 * W))
            if bad:
                raise RuntimeError(f"{bad} plate image(s) not complete before printing")
            page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

            # 3. PDF
            t = time.time()
            page.pdf(path=str(pdf_path), width=f"{W}px", height=f"{H}px",
                     print_background=True, prefer_css_page_size=True)
            report["pdf_seconds"] = round(time.time() - t, 2)
            report["baked_slides"] = [i + 1 for i in baked]
            ctx.close()
        browser.close()
    report["pdf_bytes"] = pdf_path.stat().st_size
    report["pdf"] = str(pdf_path)

    # 4. rasterise the PDF (96 dpi = 1x, 192 dpi = 2x)
    for s in scales:
        tag = f"{s}x"
        tmp = out / "pdf" / f"_r{96 * s}"
        for i, pth in enumerate(rasterise(pdf_path, 96 * s, tmp)):
            pth.replace(out / "pdf" / f"slide-{i + 1:02d}@{tag}.png")

    # 5. compare screen vs PDF: whole slide, material only (ink masked out), inside the glass
    n = len(report["dom_text"])
    for i in range(n):
        row = {"slide": i + 1}
        plate2 = load(out / "plates" / f"slide-{i + 1:02d}.png")
        for s in scales:
            tag = f"{s}x"
            scr = load(out / "screen" / f"slide-{i + 1:02d}@{tag}.png")
            pdfp = out / "pdf" / f"slide-{i + 1:02d}@{tag}.png"
            if not pdfp.exists():
                row[tag] = "missing page"; continue
            pdf = load(pdfp)
            if scr.shape != pdf.shape:
                row[tag] = f"size mismatch {scr.shape} vs {pdf.shape}"; continue
            plate_s = plate2 if s == 2 else np.asarray(
                Image.fromarray(plate2.astype(np.uint8)).resize((W, H), Image.LANCZOS)).astype(np.int16)
            ink = np.abs(scr - plate_s).max(axis=2) > 3
            k = 2 * s  # dilate ink mask so anti-aliased glyph edges count as ink
            ink_d = ink.copy()
            for dy in range(-k, k + 1):
                for dx in range(-k, k + 1):
                    ink_d |= np.roll(np.roll(ink, dy, 0), dx, 1)
            whole, d = diff_stats(scr, pdf)
            material, _ = diff_stats(scr, pdf, ~ink_d)
            inkst, _ = diff_stats(scr, pdf, ink_d)
            glass_mask = np.zeros(ink.shape, bool)
            for x, y, gw, gh in report["glass_rects"][i]:
                glass_mask[y * s:(y + gh) * s, x * s:(x + gw) * s] = True
            glass, _ = diff_stats(scr, pdf, glass_mask & ~ink_d)
            row[tag] = {"whole": whole, "material": material, "glass": glass, "ink": inkst}
            Image.fromarray(np.clip(d * 10, 0, 255).astype(np.uint8)).save(out / "diff" / f"slide-{i + 1:02d}@{tag}.png")
        report["slides"].append(row)

    # 6. text: is every word on the slide extractable from the PDF page?
    for i in range(n):
        txt = subprocess.run(["pdftotext", "-f", str(i + 1), "-l", str(i + 1), "-layout", str(pdf_path), "-"],
                             capture_output=True, text=True).stdout if shutil.which("pdftotext") else ""
        want = words(report["dom_text"][i])
        have = re.sub(r"\s+", "", txt)
        found = lambda w: w in have or ("-" in w and all(part in have for part in w.split("-") if part))  # line-wrapped hyphens
        missing = [w for w in want if not found(w)]
        report["slides"][i]["text"] = {"words": len(want), "missing": missing, "extracted": " ".join(txt.split())}

    # 7. what is inside the PDF
    if shutil.which("pdffonts"):
        report["pdf_fonts"] = subprocess.run(["pdffonts", str(pdf_path)], capture_output=True, text=True).stdout.splitlines()[2:]
    if shutil.which("pdfimages"):
        imgs = subprocess.run(["pdfimages", "-list", str(pdf_path)], capture_output=True, text=True).stdout.splitlines()[2:]
        report["pdf_images"] = [" ".join(l.split()) for l in imgs]
    if report.get("pdf_images") is not None:  # every baked page must carry exactly one plate
        per_page = {}
        for l in report["pdf_images"]:
            f = l.split()
            if f[2] == "image" and f[3] == str(2 * W):
                per_page[int(f[0])] = per_page.get(int(f[0]), 0) + 1
        bad = [p for p in report["baked_slides"] if per_page.get(p) != 1]
        report["plate_check"] = "ok" if not bad else f"missing/duplicate plate on pages {bad}"
    report.pop("dom_text", None)
    report.pop("glass_rects", None)
    report["seconds"] = round(time.time() - t0, 1)
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))

    # summary
    log(f"\n{html.name} -> {pdf_path}  ({report['pdf_bytes'] / 1e6:.2f} MB, bake={bake}, plate={plate}, "
        f"baked slides {report['baked_slides']}, {report['seconds']}s)")
    log("fonts loaded: " + ", ".join(report["fonts_loaded"]))
    def fmt(m):
        if not (isinstance(m, dict) and m.get("material")):
            return str(m)
        g = m.get("glass")
        gl = f"glass MAE {g['mae']:.2f} p99 {g['p99']}" if g else "no glass"
        return (f"material MAE {m['material']['mae']:.2f} p99 {m['material']['p99']} max {m['material']['max']}"
                f" | {gl} | ink MAE {m['ink']['mae']:.2f}")
    for r in report["slides"]:
        t = r["text"]
        log(f"slide {r['slide']:02d}  " + "  ||  ".join(f"{s}x: {fmt(r.get(f'{s}x'))}" for s in scales)
            + f"  ||  text {t['words'] - len(t['missing'])}/{t['words']} words" + (f" missing {t['missing']}" if t["missing"] else ""))
    log(f"pdf images: {len(report.get('pdf_images', []))} | pdf fonts: {len(report.get('pdf_fonts', []))} | "
        f"plate check: {report.get('plate_check', 'n/a')}")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", default=str(KIT / "test.html"))
    ap.add_argument("--out", default=str(KIT / "renders"))
    ap.add_argument("--bake", choices=["all", "marked", "none"], default="all",
                    help="all: bake every slide (default); marked: only slides with data-bake; none: live filters")
    ap.add_argument("--plate", choices=["png", "jpg"], default="png", help="plate format (jpg = smaller PDF)")
    ap.add_argument("--pdf-name", default=None)
    ap.add_argument("--scales", default="1,2", help="screen/raster scales to capture and compare, e.g. 1 or 1,2")
    ap.add_argument("--skip-fonts", action="store_true")
    args = ap.parse_args()
    render(args.html, args.out, bake=args.bake, plate=args.plate, pdf_name=args.pdf_name,
           scales=tuple(int(x) for x in args.scales.split(",")), fetch_fonts=not args.skip_fonts)
    print("report:", Path(args.out).resolve() / "report.json")


if __name__ == "__main__":
    main()
