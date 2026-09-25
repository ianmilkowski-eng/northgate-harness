# Sub-agent 3: the glass kit (design R&D)

**Role:** figure out how to render Apple-style liquid glass in HTML slides so it survives PDF export. It ran in parallel with the system builder.

**Why I split it out:** it's a pure technical question with a yes/no answer (does it look identical in the PDF?), and it can be tested without the rest of the deck. The agent built a lab page (`05-deck/glass-kit/lab.html`), tried four techniques, and diffed screen renders against rasterized PDF pages pixel by pixel. Only baking the material into a plate image survived. The table is in `05-deck/glass-kit/NOTES.md`.

## Prompt (verbatim, design tokens trimmed)

```
Prototype a production-quality "liquid glass" rendering kit for 1920x1080 HTML presentation slides, and find out which techniques survive PDF export. Work in /home/claude/deck/glass-kit/.

Context: a professional client deck (a CFO audience) built as HTML slides, exported to PDF with Playwright. The owner's taste: full liquid glass (Apple iOS 26 "Liquid Glass" look), pale blue studio background with a hint of cream, light colours only, extremely clean, must look like a senior product designer made it and must NOT look "vibe-coded".

Anti-vibe-coded rules (strict): no gradient text, no emoji, no icon-in-a-circle, no neon/glow effects, no generic blurred colour "blobs/orbs" as decoration, no bento grid of cards, no drop-shadow soup. The background must still give the glass something to refract: propose something more designed than blobs, e.g. a very soft large-scale light gradient plus a faint fine hairline grid so lensing/blur at glass edges is visible and it reads "data/ledger". Restraint over decoration.

Tasks:
1. Build test.html with two slides (a hero-number slide and a chart-in-glass slide).
2. Try these glass techniques and compare screen vs PDF: (a) CSS backdrop-filter; (b) a clipped duplicate of the background layer with CSS filter: blur()+saturate(); (c) SVG filter (feGaussianBlur / feDisplacementMap) on a duplicated background; (d) fallback: render the background+glass layer (no text) to a PNG, then place live HTML text over that image for the PDF so text stays vector/selectable.
3. Pick the technique that looks best AND is identical in the PDF. Keep text as real text in the PDF if at all possible.
4. Deliver glass.css, filter defs, fonts/, test.html, render.py, and NOTES.md (what works in PDF, what doesn't, and why).

Look at your own renders and iterate until it genuinely looks like a refined Apple-grade product slide, not a template.
```

## Follow-up: build the whole deck

The second message turned it into the deck builder. It gave it `03-specs/DECK-SPEC.md` (the copy is final) and the numbers contract. It also told it to push the material from "frosted card" to real liquid glass: lower white tint, a stronger lens band, a specular rim, a sheen, and a blue-tinted shadow.

Hard rule: every figure comes from `deck-numbers.json`, with no typed numbers. When my spec asked for a number the contract didn't have, the agent rewrote the sentence without it and reported the gap. See FAILURES.md, item 9.
