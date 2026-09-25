# What failed, and how I caught it

These are in the order they happened. Every one of them would have ended up in the deck if nothing had checked it.

## 1. The document filter dropped quoted replies

**What happened.** v0 of the filter (`01-triage/detemplate_v0.py`) splits each email into paragraphs and skips any paragraph that starts with a header line. In a forwarded chain every quoted reply starts with `> From:`. So the filter threw away whole replies, including Bev's line about holding Dr. Osei's Delta claims instead of writing them off. That line is the only proof those claims are still recoverable.

**How I caught it.** Not with the filter. I read the flagged documents in full, and the Toledo thread's subject line and first paragraph were enough to open it. Later the system-builder agent tried to cite Bev's quote from `python -m northgate triage` and noticed it wasn't in the output.

**Fix.** Strip the quote markers first, then drop only the header lines inside each quoted block and keep the body. A test now asserts Bev's line is in the triage output. The lesson: a filter tuned to throw away repetition will also throw away structure, so I spot-read what it keeps *and* what it drops.

## 2. Sentence-initial place names beat the skeleton

**What happened.** The skeleton masks capitalized words, but it skipped the first word of an utterance so that normal sentences survive. The template lines start with a place ("Florence had a patient complaint about wait times"), so each place name produced a "unique" line. v0 flagged 43 documents. 30 of them were filler.

**How I caught it.** The flagged list had lines I'd already seen repeated with different towns.

**Fix.** Mask every place name from `practices.csv` (plus Columbus and Dayton) wherever it appears. Flagged documents dropped from 43 to 13, and the 13 are exactly the real ones.

## 3. The 8 "manual" sites aren't the ones the appendix describes

**What happened.** The appendix says the 8 routing-slip sites are "the 2024 and later acquisitions". Only 6 sites were acquired in 2024 or later. My first pass would have used those 6.

**How I caught it.** Per-site gap rates in `procedures-monthly.csv`. The top 8 match Tom Kirkbride's list from the May 20 IT call exactly, and that list includes Florence (2022) and Nicholasville (2023). The data and Tom agree; the appendix is the one that's wrong. It's on the "where the documents disagree" slide now.

## 4. I nearly counted the wrong rebate contract

**What happened.** My first spec counted Patterson at 5.0% of the whole amount as the "conservative" rebate. The system-builder agent pointed out that Patterson's summary never says whether the rate applies to the whole amount or only the portion above each tier. On the marginal reading it's $73,937, not $150,187. The Henry Schein agreement says it explicitly: "applied to the entirety of Net Purchases, not marginally".

**Fix.** Count Schein at 5.5% ($165,206). Book Patterson's 2025 claim on the marginal reading ($12,510) and show $37,510 as the upper bound. The prompt told the agent to report disagreements instead of silently changing numbers, and that's the only reason this surfaced.

## 5. Rounding before multiplying

The Delta paid ratio was rounded to 0.857 before it was applied. That's $55 on $165K. Nobody would notice, but the brief says "not similar numbers, the same ones", so it now uses the unrounded ratio.

## 6. "Lowest in the company" wasn't true

The first report said Marguerite Vance had the lowest on-site hours in the company. She's the lowest of the 171 *full-time* staff; 59 part-timers log fewer. The agent caught it by actually ranking everyone. The slide says "lowest of 171 full-time staff".

## 7. "Ranked by dollars" stopped being true

When the rebate moved from $150K to $165K, it passed duplicate health plans ($158K). The slide title still said "ranked by dollars" and the order was wrong. I caught it reviewing slide 2 at full size, and the agent flagged the same thing. Ranks are now computed from value, and a test enforces the order.

## 8. Liquid glass disappears in PDF

**What happened.** CSS `backdrop-filter` is ignored when Chromium prints. The glass came out as flat panels with a sharp grid showing through. A blurred copy of the background escaped its clip and covered the text.

**Fix.** Bake it. Render each slide at 2x with all the text hidden, and put that image under the slide as the background. Then print the text and charts as live vector on top. The glass matches pixel for pixel, and every word is still selectable. The comparison of all four approaches is in `05-deck/glass-kit/NOTES.md` and `lab.html`.

## 9. The first deck spec asked for numbers that don't exist

My deck spec had copy like "6 sites acquired since 2024" and "Corporate headcount stays at 31". Those numbers weren't in the JSON contract. The deck agent refused to type them in by hand and reworded the copy instead. That was annoying in the moment and correct: every figure on a slide has to come out of the system.

## 10. The fonts I picked couldn't be installed

**What happened.** The deck was designed around Inter and Inter Tight. This build environment blocks Google Fonts, npm and GitHub, so Inter was never available offline for the PDF. The drafts rendered in a stand-in, and the web version would have loaded Inter from Google at view time. That meant two different typefaces for one deck.

**Fix.** I didn't route around the network policy. I committed to the stand-in on purpose: Instrument Sans (OFL), which ships with the glass kit. It has the precision and tabular figures I wanted from Inter, with more character at display sizes. The PDF embeds it, and the web page carries the same four weights inline, so every surface shows the exact same letters.
