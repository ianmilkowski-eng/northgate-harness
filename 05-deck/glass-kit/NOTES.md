# Glass kit: notes

Chromium 1194 (Playwright 1.56), `page.pdf(width=1920px, height=1080px, printBackground, preferCSSPageSize)`,
PDFs rasterised with poppler `pdftoppm` at 96 dpi (1x) and 192 dpi (2x). All numbers below come from
`renders/report.json` and `renders/lab/report.json`. "Glass MAE" is the mean per-pixel difference
(0-255) between the screen screenshot and the rasterised PDF inside the glass panels, with text masked out.

## Chosen technique: bake the material, keep the ink live (d)

- **On screen**, `glass.js` clones the slide's `.field` into every `.glass` and runs the clone through
  a per-panel SVG filter: a frosted body (blur 22, saturate 1.65, 36% white) plus a rim band up to 60px
  wide. In the rim, a lens map (`feDisplacementMap`) pulls the surrounding grid into the edge and curves
  it round the corners, with R and B displaced ±7% apart for a faint chromatic split, 5% white and 7%
  darker for thickness. The specular rim is vector SVG strokes (a crisp top edge fading down the sides,
  a faint darker lower rim). CSS adds a broad sheen over the top third and a large blue-tinted shadow
  (rgba(40,70,120,.07-.14)). The field has two long light bands (lavender, light blue) plus a cream
  corner. The 40/120px grid is masked to 36% strength away from the glass.
  `renders/` shows the earlier, whiter material; `/home/claude/deck/out/png/` shows this one.
- **For the PDF**, `render.py` screenshots each slide at 2x with all ink hidden (the "plate"), puts
  that plate under the slide as an `<img>`, removes the material layers and prints. Text and the
  SVG chart print as vector on top, at exactly the positions they had on screen.
- **Why:** the glass matches exactly (2x glass MAE 0.00, 1x 0.14-0.46 from resampling only), the
  scale is 1:1, every word is extractable (32/32 and 47/47), fonts are embedded as subsets with
  Unicode maps, and the result doesn't depend on how Chromium's print path treats filters.
  **Cost:** the background is a 192-dpi raster. PNG plates come to 2.25 MB for 2 slides.
  `--plate jpg` (q92, 4:4:4) gives 0.88 MB, with glass MAE 0.9 and a max of 15 at the specular edge.

## What each technique did in the PDF (`renders/lab/`, slide A rebuilt four ways)

| | technique | PDF result | glass MAE 2x |
|---|---|---|---|
| a | `backdrop-filter` on a layer behind the text | **Ignored in print**: the panel shows the sharp grid, with no blur or saturation | 2.66 (p99 7) |
| b | cloned field + CSS `filter: blur() saturate()`, clipped by `overflow:hidden` | Blurred (rasterised at 300 dpi) but **escapes the clip** and covers the hero, lede and proof | 8.86, page covered |
| c | cloned field + SVG filter (the kit engine), printed live | Rasterised at 300 dpi. The big panel is close, but **the pill loses its backdrop** and prints white. Content inside a clone can also trigger print **shrink-to-fit**: a marker in the field printed the whole page at 84% or 67% | 2.70 (p99 17) |
| d | c, baked | **Identical** | **0.00** |

Print primitives (lab slide 5):
- **Stay vector:** linear and radial gradients with alpha (including `color-mix`), SVG paths and gradient strokes, inset shadows without blur, `mix-blend-mode` (native PDF blend), `mask-image` fades.
- **Rasterised at 300 dpi (as JPEG masks) but visually the same:** blurred `box-shadow`, both outer and inset.
- **Broken:**
  - The gradient-border trick (`mask-composite: exclude`) fills the whole box and washes over that element's text. The text can still be selected, but you can't read it.
  - `filter: drop-shadow` on a text container rasterises the text, so it can't be selected.
  - `backdrop-filter` is dropped.

## Gotchas

- **Filters and text:** never put `filter`, `backdrop-filter` or `mask` on an element that contains
  text. The kit keeps the material in sibling layers with negative z-index behind the content, and
  wraps any bare text inside `.glass`.
- **Plate loading:** add the plate as an `<img>` and `await img.decode()` before `page.pdf()`. With a
  CSS `background-image` set just before printing, one run printed a slide with no plate. `render.py`
  now checks that each baked page carries exactly one 3840px image.
- **Waiting before capture:** wait for `window.__glassReady`. It fires after fonts load, after the
  panel geometry is measured (auto-width panels depend on the font) and after the lens maps decode.
  Without it, a map that hasn't loaded shifts the whole backdrop.
- **Displacement maps:** use `color-interpolation-filters="sRGB"`, or linearRGB moves the neutral 0.5.
- **Clipping filtered layers:** clip them with `clip-path` on the layer itself, not with an
  ancestor's `overflow:hidden` (see b).
- **What the glass can refract:** only the field, because it's the only thing cloned. Anything that
  must sit behind glass belongs in `.field`. Everything else is ink and goes on top.
- **Grid:** strokes use `--hairline` with `mix-blend-mode: multiply`, so they stay visible on the
  blue and lavender washes.
- **Chart colours:** the dataviz validator gives data blue vs data violet ΔE 2.4 under protanopia and
  8.6 with normal vision. Never let them be the only thing separating two series. Here the violet is
  a labelled reference rule, a different mark from the bars.
- **Hero figures:** the hero uses proportional figures (tabular "1"s look loose at 300px). Everything
  else is `tabular-nums`. Figures inside text are Inter Tight 600, and body text stays Inter 400/500.

## Fonts: action needed

The npm registry is blocked in this environment (`403 host_not_allowed`), and so are Google Fonts and
the CDNs, so Inter and Inter Tight could not be fetched. `glass.css` already points at the Fontsource
files: `fonts/inter-latin-{400,500,600}-normal.woff2` and `fonts/inter-tight-latin-{500,600}-normal.woff2`.
`render.py` runs `npm install @fontsource/inter @fontsource/inter-tight` and copies them in
automatically once the registry is reachable.

Until then the stack falls back to **Instrument Sans** (OFL, `fonts/`). Its 500 and 600 weights were
interpolated from the 400/700 masters with fontTools. Inter is about 5-8% wider, so after the swap,
re-check the one-line proof and the slide B title.

## Usage

    python3 render.py                                  # test.html -> renders/ (baked, PNG plates)
    python3 render.py --plate jpg                      # ~2.5x smaller PDF, near-identical
    python3 render.py lab.html --out renders/lab --bake marked   # technique comparison

Outputs:
- `renders/screen/slide-NN@{1,2}x.png`
- `renders/test.pdf`
- `renders/pdf/slide-NN@{1,2}x.png` (the rasterised PDF)
- `renders/plates/` and `renders/diff/` (heatmaps ×10)
- `report.json` (metrics, extracted text, embedded fonts and images)

Tune the look with the tokens in `glass.css`, globally or per panel:
- `--glass-tint`, `--glass-frost`, `--glass-saturate`
- `--glass-rim`, `--glass-lens`, `--glass-rim-tint`, `--glass-rim-shade`, `--glass-dispersion`
- `--glass-specular`, `--grid-minor`, `--grid-major`, `--grid-open`

Letter-spacing is set per element via `--ls`, and a global `--slack` term adds to it. `build.py` sets
`--slack: .04em` in a check pass to prove every line has about 8% spare width.

`render.py` also exposes `render(html, out, bake, plate, pdf_name, scales)` for scripts; the deck's
`build.py` uses it.
