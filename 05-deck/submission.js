/* Submission page behaviour: slide fitting, present mode, keys, section tracking, source browser. */
(function () {
  'use strict';
  const root = document.documentElement;
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const smooth = () => (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

  /* ---------- slides: 1920x1080, scaled into each frame once glass.js has measured them ---------- */
  const frames = $$('.frame');
  const units = $$('.unit');
  const fitOne = f => { const s = f.firstElementChild; const w = f.clientWidth; if (s && w) s.style.transform = 'scale(' + (w / 1920) + ')'; };
  const fitAll = () => frames.forEach(fitOne);
  let started = false;
  function start() {
    if (started) return;
    started = true;
    fitAll();
    root.classList.add('web-fit');
    if ('ResizeObserver' in window) {
      const ro = new ResizeObserver(es => es.forEach(e => fitOne(e.target)));
      frames.forEach(f => ro.observe(f));
    } else addEventListener('resize', fitAll);
  }
  let waited = 0;
  const poll = setInterval(() => { waited += 50; if (window.__glassReady || waited > 5000) { clearInterval(poll); start(); } }, 50);

  /* ---------- position ---------- */
  const deckSec = $('#deck');
  const deckInView = () => { const r = deckSec.getBoundingClientRect(); return r.top < innerHeight * 0.5 && r.bottom > innerHeight * 0.5; };
  const unitInView = () => { let k = 0; units.forEach((u, i) => { if (u.getBoundingClientRect().top < innerHeight * 0.45) k = i; }); return k; };
  const goUnit = i => units[Math.max(0, Math.min(units.length - 1, i))].scrollIntoView({ behavior: smooth(), block: 'start' });

  const chips = $$('.chip');
  chips.forEach(c => c.addEventListener('click', () => goUnit(+c.dataset.go)));
  const links = $$('.links a');
  const bar = $('.links');
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) return;
      const i = +e.target.dataset.i;
      chips.forEach((c, k) => c.setAttribute('aria-current', k === i ? 'true' : 'false'));
    }), { rootMargin: '-40% 0px -55% 0px' });
    units.forEach(u => io.observe(u));
    const io2 = new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) return;
      if (e.target.id === 'top' && bar.scrollLeft) bar.scrollTo({ left: 0, behavior: smooth() });
      links.forEach(a => {
        const on = a.dataset.sec === e.target.id;
        a.setAttribute('aria-current', on ? 'true' : 'false');
        if (on && bar.scrollWidth > bar.clientWidth) bar.scrollTo({ left: a.offsetLeft - (bar.clientWidth - a.clientWidth) / 2, behavior: smooth() });
      });
    }), { rootMargin: '-35% 0px -60% 0px' });
    [$('#top'), ...links.map(a => document.getElementById(a.dataset.sec))].forEach(s => s && io2.observe(s));
  }

  /* ---------- present mode: one slide at a time, fullscreen where the browser allows it ---------- */
  const web = $('#deck-web');
  const curEl = $('#p-cur');
  let cur = 0;
  const presenting = () => document.body.classList.contains('presenting');
  function show(i) {
    cur = Math.max(0, Math.min(units.length - 1, i));
    units.forEach((u, k) => u.classList.toggle('is-on', k === cur));
    curEl.textContent = cur + 1;
    requestAnimationFrame(fitAll);
  }
  function present(i) {
    if (presenting()) return;
    start();
    document.body.classList.add('presenting');
    show(i == null ? unitInView() : i);
    if (web.requestFullscreen && !document.fullscreenElement) web.requestFullscreen().catch(() => {});
  }
  function stop() {
    if (!presenting()) return;
    document.body.classList.remove('presenting');
    units.forEach(u => u.classList.remove('is-on'));
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    requestAnimationFrame(() => { fitAll(); units[cur].scrollIntoView({ block: 'start' }); });
  }
  $('#present').addEventListener('click', () => present(deckInView() ? unitInView() : 0));
  $('#p-exit').addEventListener('click', e => { e.stopPropagation(); stop(); });
  $$('.present-bar .pb[data-step]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); show(cur + +b.dataset.step); }));
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) stop(); else requestAnimationFrame(fitAll); });
  web.addEventListener('click', e => {
    if (!presenting() || e.target.closest('.present-bar')) return;
    show(cur + (e.clientX < innerWidth * 0.3 ? -1 : 1));
  });

  document.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    const k = e.key;
    if (presenting()) {
      if (k === 'Escape') { e.preventDefault(); stop(); }
      else if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(k)) { e.preventDefault(); show(cur + 1); }
      else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(k)) { e.preventDefault(); show(cur - 1); }
      else if (k === 'Home') { e.preventDefault(); show(0); }
      else if (k === 'End') { e.preventDefault(); show(units.length - 1); }
      return;
    }
    if (t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], .view, .tree, .term pre, .scroll')) return;
    if (k === 'p' || k === 'P') { e.preventDefault(); present(deckInView() ? unitInView() : 0); return; }
    if ((k === 'ArrowRight' || k === 'ArrowLeft') && deckInView()) {
      e.preventDefault();
      goUnit(unitInView() + (k === 'ArrowRight' ? 1 : -1));
    }
  });

  /* ---------- source browser ---------- */
  const src = $('.src');
  if (!src) return;
  const view = $('#src-view');
  const pathEl = $('#src-path');
  const linesEl = $('#src-lines');
  const countEl = $('#src-count');
  const segs = $$('.seg button', src);
  const trees = $$('.tree', src);
  const meta = window.__SRC_META || {};
  const NAMES = { recovery: 'northgate-recovery', harness: 'northgate-harness' };
  const last = { recovery: 'README.md', harness: 'README.md' };

  function setRepo(r) {
    segs.forEach(b => b.setAttribute('aria-pressed', b.dataset.repo === r ? 'true' : 'false'));
    trees.forEach(t => { t.hidden = t.dataset.repo !== r; });
    countEl.textContent = meta[r] || '';
  }
  function setCrumbs(r, p) {
    pathEl.replaceChildren();
    const parts = [NAMES[r]].concat(p.split('/'));
    parts.forEach((x, i) => {
      if (i) { const sep = document.createElement('i'); sep.textContent = '/'; pathEl.append(sep); }
      const s = document.createElement('span');
      s.textContent = x;
      if (i < parts.length - 1) s.className = 'dim';
      pathEl.append(s);
    });
  }
  function open(r, p, opts) {
    opts = opts || {};
    const tree = trees.find(t => t.dataset.repo === r);
    const btn = tree && [...tree.querySelectorAll('button[data-path]')].find(b => b.dataset.path === p);
    if (!btn) return false;
    setRepo(r);
    last[r] = p;
    $$('button[aria-current="true"]', src).forEach(b => b.removeAttribute('aria-current'));
    btn.setAttribute('aria-current', 'true');
    view.replaceChildren(document.getElementById(btn.dataset.tpl).content.cloneNode(true));
    view.className = 'view ' + btn.dataset.kind;
    view.scrollTop = 0;
    view.scrollLeft = 0;
    setCrumbs(r, p);
    linesEl.textContent = (+btn.dataset.lines).toLocaleString('en-US') + ' lines';
    const tr = tree.getBoundingClientRect(), br = btn.getBoundingClientRect();
    if (br.top < tr.top || br.bottom > tr.bottom) tree.scrollTop += br.top - tr.top - tr.height / 2;
    if (opts.hash !== false) { try { history.replaceState(null, '', '#source/' + r + '/' + p); } catch (err) { /* file: URLs may refuse */ } }
    if (opts.scroll) $('#source').scrollIntoView({ behavior: smooth(), block: 'start' });
    return true;
  }
  src.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.closest('.seg')) open(b.dataset.repo, last[b.dataset.repo]);
    else if (b.dataset.path) open(b.closest('.tree').dataset.repo, b.dataset.path);
  });
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[data-open]');
    if (!a) return;
    e.preventDefault();
    const v = a.dataset.open, i = v.indexOf('/');
    open(v.slice(0, i), v.slice(i + 1), { scroll: true });
  });
  const h = decodeURIComponent(location.hash || '');
  const m = h.match(/^#source\/(recovery|harness)\/(.+)$/);
  if (m && open(m[1], m[2], { hash: false })) setTimeout(() => $('#source').scrollIntoView(), 0);
  else open('recovery', 'README.md', { hash: false });
})();
