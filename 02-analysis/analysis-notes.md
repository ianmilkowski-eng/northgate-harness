# Northgate Challenge: analysis v0 (Stage 2, Straterai FDE)

*Built from the packet `SEND-stage-2-northgate.zip`. Every number below is reproducible with `findings_v0.py`, which reads `packet/data`.*

## What the assignment asks for

You submit three things, and all three are required:

1. **A deck.** 10 to 15 slides, delivered as a PDF, for Dana Reyes, the CFO. She is tired rather than hostile. The deck has to cover:
   - what you found, ranked by dollars
   - what you would build, and in what order
   - what it costs and how long it takes
   - where the work goes, naming roles
   - what you are *not* proposing
2. **A system.** A repo that runs with one command and produces exactly the numbers in the deck, traceable to rows.
3. **A harness.** A repo showing how you got through 259K words, including what failed along the way.

Scoring, in order of weight: numbers right and honest > system works > would Dana buy it > how you build > craft.

## How the documents were processed

**The de-templating filter.** Each utterance is reduced to a skeleton: capitalized words become `<C>` and digits become `<N>`. We then count how often each skeleton appears.

- 15,639 utterances and 182K words collapse to 527 skeletons.
- Only 78 long, rare utterances survive (1,942 words), which is a 99% reduction.

**Independent sweep.** A sub-agent read all 142 unflagged emails in full, re-normalized the chats and transcripts, and ran keyword checks. It found zero misses. It also found these tells:

- Every filler email is stamped `00:00:00`.
- All 14 chat channels are pure template (60 skeletons).
- Eight "serious" decoy lines are repeated 55 to 120 times, for example "three codes for the same buildup" and "$94/hr hygiene temps". Do not cite them.

**Where the signal lives.** 4 transcripts, 9 emails, 3 contracts, 2 finance docs, 2 HR docs, 4 policies and 3 OCR invoices.

## Money map (FY2025 data, annual unless noted)

| # | Finding | Gross | Realistic / notes | Join (document ↔ data) |
|---|---|---|---|---|
| 1 | **Charge-capture leak at 8 routing-slip sites.** Completed procedures never reach a claim. | $593K production | **$462K/yr net** at 78%. One-time backlog still inside filing windows is about $164K net, shrinking daily. | Tom, 5/20 IT sync ↔ `procedures-monthly`. Gap is 2.3–6.1% at the 8 sites vs a 1.0% digital baseline. |
| 2 | **Denial queue sorted by value/deadline instead of FIFO** | $1.30M write-offs/yr (ties to P&L) | **~$445K billed ≈ $353K net/yr**, assuming the same number of claims is lost but the lowest-value ones go first | SOP 3.2–3.4 ↔ `claim-denials` |
| 3 | **Duplicate legacy health plans.** 18 people are on a predecessor plan *and* the Northgate plan. | $158K/yr | ~100%. Terminating them is the sellers' obligation. | Dee thought 2 sellers (Wabash, Stonebridge). The data shows **4**, including Riverbend (2021) and Clearfork (2022). |
| 4 | **Supply rebates never collected** | $150–165K/yr steady state if volume is consolidated to one distributor. Earned-but-unclaimed at today's split is $75K/yr. | FY26 is capped by contract expiry (HS Oct 31, Patterson Nov 30): roughly $85–130K. FY25 is still claimable: $47.7K if filed by Feb 14 (HS Q4) and Mar 1 (Patterson). | Josh says "consolidated to Schein". `purchase-orders` shows a 50/50 split every month, both in the 2.5% tier. |
| 5 | **Ghost cost centers plus the Dayton retainer** | $128K/yr | NGD-23/24 is $69.9K. Halstead is $58.2K, and its FY26 capture depends on the auto-renew notice date. | Nash and Renata emails, plus 3 OCR invoices ↔ `ap-ledger`. There is no Dayton practice. |
| 6 | **Card processing** | $69K/yr | Sunbit's SaaS fee is already paid at all 22 sites, but only 5 sites process through Sunbit. BluePay/CardConnect terms are unknown. | Nash email ↔ `payment-processing` (2.42% / 2.91% / 3.38%) |
| 7 | **Osei Delta credentialing hold** (one-time) | $192.6K billed | ~$165K cash. It must be rebilled within 365 days of date of service, so the window runs **Mar 14 to Aug 21, 2026**. Nobody ever confirmed Bev's hold. | Toledo thread ↔ `claim-denials` (786 claims, 0 resubmitted) and roster PROV-024 |
| 8 | **Same-day backfill** (pilot-gated upside) | 17,099 openings. At 40% fill: $3.45M production, $1.94M contribution. | Biggest and least certain. Current fill rate is unknown, and it may pull demand forward rather than add it. Recent acquisitions run 21.7% no-show+late vs 10.1% at legacy sites. | Appendix s6 ↔ `operations-monthly` |

**Policy lever, not counted as savings:** 17 enrollees are scheduled at 28.8 to 29.6 hours/week, below the 30-hour line. That is $155K/yr gross, but acting on it is a retention call. **Small items:** zero-use licenses come to about $34K in FY26 and about $41K more at the Dec 2026 corporate renewal.

**Tiers 1–6 total about $1.32M/yr** against pre-tax of −$1.23M. FY26 capture will be lower because of ramp.

## People: where the work goes

- **Marguerite Vance, Senior AR.** She is the dashboard's most "cuttable" person: 432 claims worked, 80.8 on-site hours/month, 5 OAuth logins/month. She is also the **top recoverer, at $291K**, which works out to $674 per claim worked versus $33–34 for the two queue specialists. She was hired in 1994, which makes her a key-person risk. Protect her, and fund succession for the payer-contact knowledge she holds.
- **Billing Entry Clerks (5).** They key routing slips for the 8 sites. The reconciliation layer removes the keying without a PMS migration. Redeploy them to backlog rebilling and the ranked denial queue, and decide on attrition later.
- **Denial Queue Specialists (Odessa, Delphine).** They have the highest activity and the lowest dollar yield. Their work shifts from FIFO rekeying to a ranked queue.
- **Front Office / Eligibility (7 people at NGD-01/02).** They spend 11 minutes per patient on payer portals. Automating eligibility through the clearinghouse Northgate already pays for (DentalXChange) frees that time for the waitlist.

## Not proposing, and why

- **HQ lease exit** (the CEO's idea): locked through 2032. There is no termination clause, consent to sublet was refused twice, and the submarket has 19% vacancy.
- **Cutting RCM:** write-offs would rise.
- **Cutting Marguerite:** she is the top recoverer (see People above).
- **PMS migration:** $144–240K plus 6–10 weeks per site.
- **Imaging:** tied to the hardware.
- **Corporate software:** under contract until Dec 2026.
- **Supply "utilization" at the surgical sites:** it reflects clinical mix. Grantley's 8–15% has no price data behind it.
- **Patient-comms consolidation:** the Q1 2025 attempt already failed.
- **Payer renegotiation beyond UC (Mar) and Guardian (Sep).**
- **Sub-30-hour benefits clawback.**

## Where the documents are wrong (worth a slide)

- **Appendix:** says the 8 manual sites are "2024+ acquisitions". The data and Tom both include Florence (2022) and Nicholasville (2023).
- **Tom:** says "14 on the same platform". The 14 run four different PMS brands, so the difference is the billing integration, not the PMS.
- **Josh:** says supply was consolidated to Schein. It was not.
- **Dee:** says two sellers never terminated their plans. It was four.
- **P&L tie-outs:**
  - Corporate payroll uses $52K for all 14 RCM staff, but Marguerite earns $71.4K, so loaded cost is understated by $23.5K.
  - $46K of Dentrix/Weave charges at NGD-23/24 sit in AP but not in `vendor-spend` or the P&L software line.

## Open questions for Charlie/James

1. What is "today" in Northgate's world? The answer decides whether the Osei rebill, the FY25 rebate filings and the unbilled backlog are still recoverable.
2. Did Schein's rep confirm whether any HS-VR-4 was ever filed?
3. What are the termination terms for the NGD-23/24 contracts, and when exactly is Halstead's MSA anniversary?
4. Do the BluePay and CardConnect contracts have early-termination fees?

## Ian's aesthetic (stated by Ian, 2026-09-24; this overrides anything inferred from Drive)

- **Surface:** liquid glass.
- **Palette:** light colors throughout. Light blue and light purple, with cream and white.
- **Type:** a consistent font or font system.
- **Tone:** very simple, and genuinely useful with the data that's there.
- **The rule:** it must look like a professional designer made it. **Never "vibe-coded"** — that's his biggest pet peeve.
- **Do NOT use the Baldwin Times style.** VERTE (sage, forest green and gold, editorial) was an earlier project and is not the direction either.
- **Build note:** his past decks are image-built, with no text layer. This deck has to be code-rendered so every figure matches the system output exactly.

### Locked design direction (aesthetic interview, 2026-09-24)

1. **Glass:** full liquid glass, iOS 26 style. Refractive glass slabs with specular edge highlights over a soft color field. The glass has to survive PDF export, so it is rendered as real layers, not only with CSS `backdrop-filter`.
2. **Color field:** "pale blue studio" with a hint of cream.
   - Base: `#EEF3F9` pale blue-gray, warmed with cream `#F7F4EE`.
   - Panels: white glass.
   - Accents: lavender `#B9A8F0`.
   - Ink: `#18202E`.
   - Data colors: blue `#5A86D8` and violet `#9A86E0`.
3. **Type:** Inter Tight for headlines and hero numbers, Inter for body and labels. Tabular figures throughout.
4. **Data style:** one number, one proof. Each finding slide gets:
   - a hero number
   - a one-line takeaway
   - one small chart that proves it
   - a quiet source line citing the exact file and rows

   Detail lives in the HTML version.
5. **Anti-vibe-coded rules:**
   - No gradient text, emoji, icon-in-circle grids, glows or neon.
   - No bento grid of rounded cards on every slide.
   - Glass gets a job (layering and focus).
   - One type scale, hairline rules, generous whitespace, one accent per slide.
