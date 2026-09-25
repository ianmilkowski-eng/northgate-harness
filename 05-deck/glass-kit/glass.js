/* ==========================================================================
   glass.js · builds the field grid and the liquid-glass material
   --------------------------------------------------------------------------
   For every .field  : draws the engineering grid (--unit cells, a major line
                       every --grid-major-every cells), one vector path each,
                       stroked with --hairline, plus the cream key light.
   For every slide   : masks that grid so it is quiet in open areas and fully
                       present around the glass, where the lens bends it.
   For every .glass  : inserts, behind its content,
     .glass__backdrop  a clone of the slide's field, aligned to the slide and
                       run through a per-panel SVG filter (defs below):
                         body = blur + saturate + light white tint
                         rim  = lightly blurred field bent by a lens map
                                (feDisplacementMap), R and B displaced a few
                                percent apart (faint chromatic split), a touch
                                darker (thickness), masked to a band along the
                                rounded edge
     .glass__rim       vector specular: a crisp top rim fading down the sides,
                       a faint darker lower rim, a hairline edge all round.
   Text never sits inside a filtered layer, so it stays vector in the PDF.
   Signals completion with html.glass-ready + window.__glassReady = true.
   Opt out per element with data-glass="manual"; window.glassKitAfter (sync or
   async) runs after enhancement and before the ready signal.
   ========================================================================== */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const root = document.documentElement;
  const css = getComputedStyle(root);
  const num = (name, fallback, el) => {
    const v = parseFloat((el ? getComputedStyle(el) : css).getPropertyValue(name));
    return Number.isFinite(v) ? v : fallback;
  };
  const cfg = {                                   // fallbacks mirror the tokens in glass.css
    unit: num('--unit', 40), every: num('--grid-major-every', 3),
    gridMinor: num('--grid-minor', .30), gridMajor: num('--grid-major', .64), gridOpen: num('--grid-open', .42),
    base: css.getPropertyValue('--field').trim() || '#EEF3F9',
    hairline: css.getPropertyValue('--hairline').trim() || '#D9E2EE',
  };
  const TOKENS = {                                 // per-glass overridable material tokens
    frost: ['--glass-frost', 22], saturate: ['--glass-saturate', 1.65], tint: ['--glass-tint', .36],
    rimTint: ['--glass-rim-tint', .05], rim: ['--glass-rim', 46], lens: ['--glass-lens', 48],
    rimBlur: ['--glass-rim-blur', .6], rimCurve: ['--glass-rim-curve', 1.5],
    dispersion: ['--glass-dispersion', .07], spec: ['--glass-specular', 1], shade: ['--glass-rim-shade', .07],
  };

  /* ---------- field ---------- */
  function gridPath(w, h, step, skip) {
    let d = '';
    for (let x = step; x < w; x += step) if (!skip || x % skip) d += `M${x + .5} 0V${h}`;
    for (let y = step; y < h; y += step) if (!skip || y % skip) d += `M0 ${y + .5}H${w}`;
    return d;
  }
  const MAJOR_STEP = cfg.unit * cfg.every;
  const MINOR = gridPath(1920, 1080, cfg.unit, MAJOR_STEP);
  const MAJOR = gridPath(1920, 1080, MAJOR_STEP, 0);
  function buildField(field) {
    if (field.querySelector('.field__grid')) return;
    field.insertAdjacentHTML('beforeend',
      `<svg class="field__grid" width="1920" height="1080" viewBox="0 0 1920 1080" aria-hidden="true"><g class="field__lines">` +
      `<path d="${MINOR}" fill="none" stroke="${cfg.hairline}" stroke-opacity="${cfg.gridMinor}" stroke-width="1" shape-rendering="crispEdges"/>` +
      `<path d="${MAJOR}" fill="none" stroke="${cfg.hairline}" stroke-opacity="${cfg.gridMajor}" stroke-width="1" shape-rendering="crispEdges"/>` +
      `</g></svg><div class="field__light"></div>`);
  }
  // quiet the grid in open areas: full strength within ~90px of any glass, --grid-open elsewhere
  let maskN = 0;
  function maskGrid(field, rects) {
    const svg = field && field.querySelector('.field__grid');
    if (!svg || svg.querySelector('mask') || !rects.length) return;
    const id = 'gridmask-' + (++maskN), v = Math.round(255 * cfg.gridOpen);
    const shapes = rects.map(q => `<rect x="${q.x - 70}" y="${q.y - 70}" width="${q.w + 140}" height="${q.h + 140}" rx="${q.r + 70}" fill="#fff"/>`).join('');
    svg.insertAdjacentHTML('afterbegin',
      `<defs><filter id="${id}-b" filterUnits="userSpaceOnUse" x="-200" y="-200" width="2320" height="1480"><feGaussianBlur stdDeviation="46"/></filter>` +
      `<mask id="${id}" maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080" style="mask-type:luminance">` +
      `<rect width="1920" height="1080" fill="rgb(${v},${v},${v})"/><g filter="url(#${id}-b)">${shapes}</g></mask></defs>`);
    svg.querySelector('.field__lines').setAttribute('mask', `url(#${id})`);
  }

  /* ---------- lens map ----------
     R,G: displacement (128 = none), B: rim weight. The signed distance to the
     rounded rectangle gives the depth t from the edge; the outward normal n
     comes from the same rectangle with a radius of at least the rim width, so
     it turns smoothly round the corners (no seam where the rim is wider than
     the corner radius). Inside the rim band the backdrop is sampled along +n,
     by up to --glass-lens px at the very edge: the band [0, rim] shows the
     strip [-lens, rim] compressed and never mirrored, so lines that surround
     the panel bunch up against its border and curve round its corners.     */
  function lensMap(w, h, r, rim, curve) {
    const W = Math.round(w), H = Math.round(h);
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const ctx = c.getContext('2d');
    const img = ctx.createImageData(W, H), d = img.data;
    const hw = W / 2, hh = H / 2, rr = Math.min(r, hw, hh), rn = Math.min(Math.max(r, rim * 1.15), hw, hh);
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const px = x + .5 - hw, py = y + .5 - hh, ax = Math.abs(px), ay = Math.abs(py);
        const qx = ax - (hw - rr), qy = ay - (hh - rr);
        const t = Math.max(-(Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - rr), 0);
        let nx = 0, ny = 0;
        if (t < rim) {
          const sx = ax - (hw - rn), sy = ay - (hh - rn);
          if (sx > 0 && sy > 0) { const l = Math.hypot(sx, sy); nx = sx / l; ny = sy / l; } else if (sx > sy) nx = 1; else ny = 1;
          if (px < 0) nx = -nx; if (py < 0) ny = -ny;
        }
        const k = t < rim ? 1 - t / rim : 0;
        const m = Math.pow(k, 1.5);                   // displacement profile (monotone compression)
        const wgt = Math.pow(k, curve);               // rim visibility profile
        const i = (y * W + x) * 4;
        d[i]     = Math.round(127.5 + 127.5 * m * nx);  // sample outward along n
        d[i + 1] = Math.round(127.5 + 127.5 * m * ny);
        d[i + 2] = Math.round(255 * wgt);
        d[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return c.toDataURL('image/png');
  }

  /* ---------- filter defs (one per panel: the lens map is size-specific) ---------- */
  const lerpWhite = a => { const k = (1 - a).toFixed(4), o = a.toFixed(4);
    return `${k} 0 0 0 ${o}  0 ${k} 0 0 ${o}  0 0 ${k} 0 ${o}  0 0 0 1 0`; };
  const CH = { r: '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0', g: '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0', b: '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0' };
  function filterDef(id, w, h, map, o) {
    const B = Math.ceil(o.frost * 3.2), S = 2 * o.lens, dsp = (s, res) =>
      `<feDisplacementMap in="clear" in2="map" scale="${s.toFixed(2)}" xChannelSelector="R" yChannelSelector="G" result="${res}"/>`;
    return `<filter id="${id}" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
        x="${-B}" y="${-B}" width="${w + 2 * B}" height="${h + 2 * B}" color-interpolation-filters="sRGB">
      <feFlood flood-color="${cfg.base}" result="base"/>
      <feMerge result="src"><feMergeNode in="base"/><feMergeNode in="SourceGraphic"/></feMerge>
      <feGaussianBlur in="src" stdDeviation="${o.frost}" result="body0"/>
      <feColorMatrix in="body0" type="saturate" values="${o.saturate}" result="body1"/>
      <feColorMatrix in="body1" type="matrix" values="${lerpWhite(o.tint)}" result="body"/>
      <feImage href="${map}" x="0" y="0" width="${w}" height="${h}" preserveAspectRatio="none" result="map"/>
      <feGaussianBlur in="src" stdDeviation="${o.rimBlur}" result="clear"/>
      ${dsp(S * (1 + o.dispersion), 'dR')}${dsp(S, 'dG')}${dsp(S * (1 - o.dispersion), 'dB')}
      <feColorMatrix in="dR" type="matrix" values="${CH.r}" result="cR"/>
      <feColorMatrix in="dG" type="matrix" values="${CH.g}" result="cG"/>
      <feColorMatrix in="dB" type="matrix" values="${CH.b}" result="cB"/>
      <feComposite in="cR" in2="cG" operator="arithmetic" k2="1" k3="1" result="cRG"/>
      <feComposite in="cRG" in2="cB" operator="arithmetic" k2="1" k3="1" result="bent0"/>
      <feColorMatrix in="bent0" type="saturate" values="${(o.saturate * 1.15).toFixed(3)}" result="bent1"/>
      <feColorMatrix in="bent1" type="matrix" values="${lerpWhite(o.rimTint)}" result="bent2"/>
      <feComponentTransfer in="bent2" result="bent"><feFuncR type="linear" slope="${(1 - o.shade * 1.15).toFixed(4)}"/><feFuncG type="linear" slope="${(1 - o.shade).toFixed(4)}"/><feFuncB type="linear" slope="${(1 - o.shade * .55).toFixed(4)}"/></feComponentTransfer>
      <feColorMatrix in="map" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 1 0 0" result="rimMask"/>
      <feComposite in="bent" in2="rimMask" operator="in" result="rim"/>
      <feMerge><feMergeNode in="body"/><feMergeNode in="rim"/></feMerge>
    </filter>`;
  }

  /* ---------- specular rim (vector) ---------- */
  function rimSVG(id, w, h, r, spec = 1) {
    const q = v => Math.min(1, v * spec).toFixed(3), rx = k => Math.max(0, r - k);
    const st = (o, a, c = '#fff') => `<stop offset="${o}" stop-color="${c}" stop-opacity="${q(a)}"/>`;
    const fade = Math.min(1, Math.max(.3, 150 / h));          // the top rim is gone ~150px down the sides
    return `<svg class="glass__rim" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <defs>
        <linearGradient id="${id}-top" gradientUnits="objectBoundingBox" x1="0" y1="0" x2="0" y2="1">${st(0, 1)}${st((r / h * .9).toFixed(3), .9)}${st(fade.toFixed(3), 0)}</linearGradient>
        <linearGradient id="${id}-low" gradientUnits="objectBoundingBox" x1="0" y1="0" x2="0" y2="1">${st(.55, 0, '#28467A')}${st(1, .30, '#28467A')}</linearGradient>
      </defs>
      <rect x=".5" y=".5" width="${w - 1}" height="${h - 1}" rx="${rx(.5)}" fill="none" stroke="#fff" stroke-opacity="${q(.28)}" stroke-width="1"/>
      <rect x=".75" y=".75" width="${w - 1.5}" height="${h - 1.5}" rx="${rx(.75)}" fill="none" stroke="url(#${id}-top)" stroke-width="1.5"/>
      <rect x="1.5" y="1.5" width="${w - 3}" height="${h - 3}" rx="${rx(1.5)}" fill="none" stroke="url(#${id}-low)" stroke-width="1"/>
    </svg>`;
  }

  /* ---------- enhance ---------- */
  function defsHost() {
    let svg = document.getElementById('glass-defs');
    if (!svg) {
      svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('id', 'glass-defs'); svg.setAttribute('aria-hidden', 'true');
      svg.setAttribute('width', '0'); svg.setAttribute('height', '0');
      svg.style.position = 'absolute';
      svg.appendChild(document.createElementNS(NS, 'defs'));
      document.body.prepend(svg);
    }
    return svg.querySelector('defs');
  }

  function measure(glass) {
    const slide = glass.closest('.slide');
    const field = slide && slide.querySelector(':scope > .field');
    if (!field || glass.dataset.glass === 'manual' || glass.querySelector(':scope > .glass__backdrop')) return null;
    [...glass.childNodes].forEach(nd => {           // bare text gets a wrapper so export passes can hide it
      if (nd.nodeType === 3 && nd.textContent.trim()) {
        const s = document.createElement('span'); s.className = 'glass__text';
        nd.replaceWith(s); s.appendChild(nd);
      }
    });
    const sr = slide.getBoundingClientRect(), gr = glass.getBoundingClientRect();
    const r = parseFloat(getComputedStyle(glass).borderTopLeftRadius) || 0;
    const o = {};
    for (const [k, [name, fb]] of Object.entries(TOKENS)) o[k] = num(name, fb, glass);
    const short = Math.min(gr.width, gr.height);
    o.rim = Math.min(o.rim, short * .42);
    o.lens = Math.min(o.lens, o.rim * 1.05);
    return { glass, slide, field, x: gr.left - sr.left, y: gr.top - sr.top, w: gr.width, h: gr.height, r, o };
  }

  async function enhance(p, n, defs) {
    const { glass, field, x, y, w, h, r, o } = p;
    glass.style.setProperty('--gx', x + 'px');
    glass.style.setProperty('--gy', y + 'px');
    const id = 'glass-' + n;
    const map = lensMap(w, h, r, o.rim, o.rimCurve);
    const pre = new Image(); pre.src = map;
    try { await pre.decode(); } catch (e) { /* data URL: decode is best-effort */ }
    defs.insertAdjacentHTML('beforeend', filterDef(id, w, h, map, o));
    const bd = document.createElement('div');
    bd.className = 'glass__backdrop';
    bd.setAttribute('aria-hidden', 'true');
    bd.appendChild(field.cloneNode(true));
    bd.style.filter = `url(#${id})`;
    glass.prepend(bd);
    bd.insertAdjacentHTML('afterend', rimSVG(id, w, h, r, o.spec));
  }

  async function run() {
    document.querySelectorAll('.field').forEach(buildField);
    await document.fonts.ready;
    const defs = defsHost();
    const plan = [...document.querySelectorAll('.glass')].map(measure).filter(Boolean);   // measure before anything moves
    const bySlide = new Map();
    plan.forEach(p => { if (!bySlide.has(p.slide)) bySlide.set(p.slide, []); bySlide.get(p.slide).push(p); });
    bySlide.forEach((ps, slide) => maskGrid(slide.querySelector(':scope > .field'), ps));  // before the fields are cloned
    await Promise.all(plan.map((p, i) => enhance(p, i, defs)));
    if (typeof window.glassKitAfter === 'function') await window.glassKitAfter();   // optional page hook
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    root.classList.add('glass-ready');
    window.__glassReady = true;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
