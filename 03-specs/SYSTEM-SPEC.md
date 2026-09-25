# SPEC — northgate-recovery (system repo for the Straterai Northgate challenge)

Build a small, production-quality Python package that runs against `packet/data/*.csv` and prints every number the deck uses, with each number traceable to the exact source rows. Graders will clone this on a clean machine: **one command to install, one command to run.** Only dependency: `pandas>=2.0` (pytest for tests only). No notebooks. Python 3.10+.

`findings_v0.py` in this folder is the reference implementation of most numbers. `detemplate.py` is the document triage filter. Re-structure them; do not change the math unless this spec says so. Delete both reference files from the repo root at the end (move detemplate logic into the package).

## Layout
```
README.md                 # what it is, install, run, commands, how to trace a number, assumptions table, what is NOT counted
requirements.txt          # pandas>=2.0
packet/                   # the challenge packet (already copied; do not modify)
northgate/
  __init__.py
  __main__.py             # CLI entry: python -m northgate <command> [--as-of YYYY-MM-DD] [--packet PATH] [--out DIR]
  assumptions.py          # every assumption/fact: value, source doc path, verbatim quote (see list below)
  load.py                 # CSV loaders; add `_line` column = original CSV line number (header = line 1, first data row = line 2)
  model.py                # Finding dataclass + JSON serialisation
  findings/  charge_capture.py  denial_priority.py  duplicate_plans.py  rebates.py  ghost_spend.py
             card_processing.py credential_hold.py  backlog.py  backfill.py  people.py  licenses.py  sub30_benefits.py
  tieouts.py              # P&L and cross-file tie-out checks
  triage.py               # document de-templating filter (from detemplate.py), prints rare utterances by document
  report.py               # plain-text terminal rendering (no colour libs)
out/                      # generated (gitignore it): findings.json + evidence/<finding_id>.csv
tests/test_numbers.py     # asserts every expected value below (tolerance: exact to the dollar after rounding)
tests/test_quotes.py      # asserts every quote in assumptions.py appears verbatim in its source document
.gitignore
```

## CLI
- `python -m northgate` (= `run`): compute everything, print the report, write `out/findings.json` and `out/evidence/*.csv`.
- `python -m northgate explain <finding_id>`: print title, headline, method (3–6 lines), assumptions with doc quotes, sources, and the first 15 evidence rows; say where the full CSV is.
- `python -m northgate list`: ids + one-line titles.
- `python -m northgate tieouts`: print tie-out table.
- `python -m northgate triage`: run document filter over `packet/documents`, print stats (utterances, words, skeletons, rare lines, % reduction) and rare utterances grouped by document.
- `--as-of` default `2026-02-02` (affects only deadline-bound one-time items: backlog, credential hold, rebate filing status). Print the as-of date in the report header.

## Finding object (model.py)
Fields: `id, rank (int|None), title, headline (one sentence), category` in {`run_rate`,`one_time`,`upside`,`policy`,`small`}, `annual_net` (float|None), `gross` (float|None), `fy2026` (dict|None, e.g. scenarios), `one_time_value` (float|None), `confidence` in {`measured`,`contractual`,`modeled`,`assumption-led`}, `method` (list of str), `assumptions` (list of assumption ids), `sources` (list of {file, rows, filter}), `docs` (list of {path, quote}), `metrics` (dict — chart data for the deck, see per-finding), `evidence_csv` (path), `evidence_rows` (int). Evidence CSVs must include `source_file` and `source_line` columns plus the computed columns.

## Global constants (assumptions.py) — each with source path + verbatim quote
- NET_COLLECTION = 0.78 (northgate-overview.md "Net collection rate on submitted claims: **78%** of gross production" — quote the exact text in the file)
- CONTRIBUTION_MARGIN = 0.72; FILL_RATE = 0.40 (appendix §6); LOADED_MULTIPLIER = 1.21
- TIMELY_FILING = {Medicaid: 90, commercial: 180} days from DOS; APPEAL_DAYS = 60
- DELTA_RETRO_DAYS = 365 (appendix §11)
- HS tiers {0:0, 1.0M:2.5%, 1.75M:4.0%, 2.5M:5.5%} whole-amount; HS quarterly Form HS-VR-4 within 45 days else forfeited; HS term ends 2026-10-31; Schedule A aggregation clause (contracts/2023-henry-schein-master-agreement-excerpt.txt)
- Patterson tiers {0:0, 1.0M:2.5%, 1.75M:4.0%, 2.5M:5.0%}; annual certification within 60 days of year end; ends 2026-11-30 (contracts/2023-patterson-supply-agreement-summary.txt)
- SLIP_SITES = NGD-12, 16, 17, 18, 19, 20, 21, 22 (sources: transcripts/2025-05-20-it-integration-sync.txt Tom's list; employees.csv Billing Entry Clerk duties). NOTE in README: the appendix says "2024 and later acquisitions" but NGD-12 (2022) and NGD-16 (2023) are in Tom's list and the data confirms them.
- Halstead MSA 02/2023, auto-renews unless cancelled 60 days before anniversary (invoices/2025-09-halstead-creative-SCANNED.txt — OCR text, quote as it appears)
- Benefits eligibility 30 h/week (policies/benefits-eligibility.txt); predecessor-plan termination is seller's obligation (same file)
Quotes must be copied verbatim from the files (OCR typos included). test_quotes.py enforces this.

## Findings and EXACT expected values (round to nearest dollar unless noted)

### 1 `charge_capture` — run_rate, measured, rank 1
Procedures completed but never submitted to a claim, at the 8 routing-slip sites, **in excess of** the 14 digital sites' baseline gap rate.
- gap = procedures_completed − procedures_submitted_to_claim (procedures-monthly.csv)
- baseline = Σgap / Σcompleted over the 14 non-slip sites = **0.998%** (0.00998…)
- excess_value per slip row = (gap − completed × baseline) × avg_procedure_value_usd; Σ = **$592,915**
- annual_net = × NET_COLLECTION = **$462,474**
- metrics: per-site {site, name, gap_pct, is_slip, excess_value} for all 22 sites; baseline_pct.
- evidence: the 96 slip-site rows (plus a second CSV or section with the 168 baseline rows is fine).
- docs: Tom (2025-05-20 IT sync, "Nobody checks..."), SOP 1.2–1.3, clerk duty statement.

### 2 `denial_priority` — run_rate, modeled, rank 2
Denials are worked FIFO (SOP 3.2–3.3); ~30% age past the filing limit. Model: the **same number of claims** is still lost (5,033), but the queue is ordered by value so the lost ones are the lowest-value claims.
- row avg = denied_amount_usd / denied_claims; written-off $ per row = avg × written_off_past_filing_limit; Σ = **$1,299,672** (P&L line: $1,300,094.73 — pro-rata method difference $423)
- exclude reason "Provider not credentialed with payer" (held, not written off) from the pool; expand to claim level at row-average value; sort ascending; lowest 5,033 claims sum to **$854,995**
- billed_saved = **$444,677**; annual_net = × NET_COLLECTION = **$346,848**
- metrics: write-offs by reason (8 reasons: claims, $ written off), by payer; fifo_writeoff, value_first_writeoff.
- docs: SOP 3.2–3.4; appendix §4 quote about FIFO.

### 3 `duplicate_plans` — run_rate, measured, rank 3
Employees enrolled in a predecessor ("LEG-") plan AND a Northgate plan (benefits-enrollment.csv plan_id startswith "LEG").
- **18** people, **4** sponsoring entities (Clearfork, Riverbend, Stonebridge, Wabash), monthly **$13,195.44**, annual **$158,345**
- metrics: per seller {entity, people, monthly, annual, acquisition year}; note HR's email names only Wabash and Stonebridge.
- docs: 2025-08-19 Dee email; benefits policy acquired-employees clause.

### 4 `rebates` — run_rate, contractual, rank 4
- 2025 POs: HS **$1,503,335.21**, Patterson **$1,500,403.70**, total **$3,003,738.91**; monthly HS share 49.5%–50.6%.
- earned at current split (both 2.5%) **$75,093**; collected **$0** (no rebate lines in AP / P&L).
- steady state if consolidated: Patterson 5.0% = **$150,187** (counted in total, conservative); HS 5.5% = **$165,206** (upside; depends on Schedule A covering all sites + quarterly filings).
- fy2026 scenarios (use 2025 monthly volumes as the 2026 forecast; Patterson counts Jan–Nov, HS Jan–Oct; months before the switch keep their 2025 split): switch Patterson Feb 1 → **$129,595** (5.0%); Mar 1 → **$99,079** (4.0% — below the $2.5M cliff: vol $2,476,975); Apr 1 → **$93,970**; HS never reaches 5.5% in 2026 (Feb switch: $93,643). Stay split but file everything: **$64,626**.
- one-time (FY2025 still claimable): HS Q4-2025 $405,913.80 × 2.5% = **$10,148** (deadline 2026-02-14); Patterson FY2025 × 2.5% = **$37,510** (deadline 2026-03-01); total **$47,658**. Mark each deadline as open/closed relative to --as-of.
- Schedule A risk: HS 2025 excluding NGD-17..22 = $1,053,090.
- docs: Renata 2025-07-22 email; Josh 2025-03-11 transcript ("We consolidated everything to Henry Schein last year."); both contracts.

### 5 `ghost_spend` — run_rate, measured, rank 5
- AP rows with practice_id NGD-23 or NGD-24 (not in practices.csv): **$69,898.98** (Dentrix, Weave, Spectrum Business, Vector Security, Cintas — 12 months each)
- Halstead Creative Group "Dayton market retainer" (CORP): **$58,200** — there is no Dayton-area practice in practices.csv.
- annual **$128,099**. fy2026 note: Halstead auto-renewal notice window likely passed for the Feb-2026 anniversary → FY26 capture of Halstead $0–$48,500; ghost services ~11 months.
- metrics: per cost-center × vendor annual; the 3 OCR invoice facts (Spectrum active since 03/2023; Vector: no open/close activity).
- Also note (tie-out): $46,064 of the NGD-23/24 Dentrix+Weave charges are absent from vendor-spend.csv, i.e. invisible in the P&L software line.

### 6 `card_processing` — run_rate, measured, rank 6
- effective rate by processor (fees/volume): Sunbit 2.422%, BluePay 2.913%, CardConnect (legacy) 3.384%.
- savings if BluePay and CardConnect volume paid Sunbit's effective rate: **$69,101**.
- vendor-spend shows Sunbit's SaaS fee is already paid at all 22 sites (contract to 2027-01-31) while only 5 sites process through Sunbit.
- metrics: per processor {sites, volume, fees, rate}.

### 7 `credential_hold` — one_time, measured
- claim-denials rows reason "Provider not credentialed with payer": all NGD-13 Delta Dental, Mar–Aug 2025: **786** claims, **$192,643.36**, 0 resubmitted, 0 written off.
- expected cash = billed × Delta paid/submitted at NGD-13 in credentialed months (2025-01, 02, 09, 10, 11, 12 from claims-monthly) = **0.857** → **$165,095**.
- roster: PROV-024 Dr. Amara Osei, credential_term 2025-03-14, reinstated 2025-08-22.
- rebill windows close 365 days after DOS: **2026-03-14 → 2026-08-21**. Report days remaining vs --as-of.
- metrics: monthly denied $ Mar–Aug; Delta NGD-13 paid ratio by month (shows the collapse).
- docs: 2025-11-06 Toledo thread (Bev: "I have been holding them rather than writing them off...").

### 8 `backlog` — one_time, measured, as-of dependent
Excess unbilled value (from finding 1) whose DOS is still inside the filing window at --as-of. Assume DOS uniform within the month. Payer split per site from claims-monthly amount_submitted shares; Medicaid 90 days, commercial 180 days, "Self-pay / Uninsured" share excluded.
- at 2026-02-02: gross **$207,604** → net **$161,931**. metrics: by month.

### 9 `backfill` — upside, assumption-led (NOT in totals)
- openings = no_shows + late_cancellations (appendix §13 says treat together) = **17,099**
- at FILL_RATE 40%: production = Σ openings × 0.40 × (gross_production / appointments_completed) per row = **$3,449,640**; contribution = × 0.78 × 0.72 = **$1,937,318**
- cohort metric: 6 recent sites (NGD-17..22) openings rate **21.7%** vs 16 legacy **10.1%**
- method notes: current fill rate unmeasured; some fills pull demand forward; NGD-22 Jan–May is ramp → pilot before counting.

### 10 `people` — the telemetry trap (no $ total)
From denial-worklog, network-activity, employees:
- E-0300 Marguerite Vance (Senior AR Specialist): 432 claims worked, **$291,156** recovered (team #1), **$674** per claim worked, on-site **80.8** h/mo (lowest in company), OAuth **5.0**/mo; hired 1994-10-17.
- E-0304 Odessa Yerkes / E-0307 Delphine Marchbanks (Denial Queue Specialists): 2,487 / 2,578 claims, $84,371 / $85,735, **$33.9 / $33.3** per claim, on-site 176/179 h/mo, OAuth 224/245.
- E-0294..E-0298 Billing Entry Clerks (5): duty statement = keying routing slips for the 8 sites.
- metrics: all 14 RCM staff {id, name, title, claims, recovered, per_claim, onsite_hrs, oauth}.

### 11 `licenses` — small (not in totals)
Zero sessions in last 90 days (software-usage.csv): FY26-addressable (PMS, patient comms, intake, reviews) **91 seats $34,422**; corporate NetSuite/Tableau/M365 **47 seats $41,024** (contract to 2026-12-31); clearinghouse **27 seats $9,180** (to 2027-01-31); imaging **21 seats $8,657** (treated as fixed, appendix §3).

### 12 `sub30_benefits` — policy (not in totals)
Northgate-plan enrollees with fte × 40 < 30: **17** people, **$155,444**/yr employer premium. Frame as a retention decision, not a saving.

## Totals (report header + findings.json.totals)
- run_rate (1–6): 462,474 + 346,848 + 158,345 + 150,187 + 128,099 + 69,101 = **$1,315,054**
- one_time (7 + 8 + rebates FY2025 claims): 165,095 + 161,931 + 47,658 = **$374,684**
- upside (9): **$1,937,318** (not counted)
- context from pnl-fy2025.csv: EBITDA 3,921,446.46; interest 2,244,000; pre-tax −1,232,553.54 → run_rate would move pre-tax to ≈ **+$82,500** (state as illustrative, full-year run-rate).

## Tie-outs (tieouts.py) — print file vs P&L, diff, verdict
- Gross production: operations-monthly 55,511,000.38 vs P&L 55,511,000.41 (ties)
- Dental supplies: operations-monthly 2,999,662.37 = P&L; purchase-orders 3,003,738.91 (diff 4,076.54 — PO timing)
- Denial write-offs: pro-rata 1,299,671.88 vs P&L 1,300,094.73 (method rounding)
- Clinical payroll: payroll-summary practices 22,811,158.83 vs P&L 22,811,158.82 (ties)
- Corporate payroll: payroll-summary 3,304,510 = P&L, BUT employees.csv CORP base × 1.21 = 3,327,984 → P&L understated by **$23,474** (Marguerite at $71,400 vs $52,000 RCM standard)
- Software: vendor-spend 1,149,388.96 vs P&L 1,149,388.93 (ties) — but AP carries $46,064 of NGD-23/24 Dentrix+Weave not in vendor-spend
- Denied $: claims-monthly 4,742,038.83 vs claim-denials 4,385,442.59 (diff 356,596.24 — the two billing files disagree; we use claim-denials, which ties to the P&L write-off line)

## findings.json
Top level: `as_of, generated_at, packet_path, totals, context, findings[] (all 12, ordered: run_rate by rank, then one_time, upside, people, small, policy), tieouts[], not_proposing[]`.
`not_proposing` = list of {item, reason, source} for: HQ lease exit (legal memo 2024-09-04: runs to 2032, no termination/contraction, consent refused twice, 19.2% vacancy); cutting RCM headcount (appendix §2; Dana 2025-10-01 email); cutting Marguerite Vance (finding people); PMS migration of 8 sites ($18–30K/site, 6–10 weeks, appendix §3); imaging consolidation ($22–40K/operatory); corporate software (contract to Dec 2026); supply utilization at surgical sites NGD-10/NGD-17 (appendix §5, clinical mix); patient-comms consolidation (failed Q1 2025); payer renegotiation beyond United Concordia (Mar) / Guardian (Sep); removing coverage from sub-30h enrollees (policy).

## Quality bar
- Code a client's team would be comfortable inheriting: small functions, docstrings, no magic numbers outside assumptions.py, type hints.
- `python -m northgate` must run in < 10 s and print a clean, aligned report (money with thousands separators, right-aligned).
- `pytest -q` passes. Include a test that the run_rate total equals the sum of its parts and equals 1,315,054.
- README: 1) one-paragraph what/why; 2) Install `pip install -r requirements.txt`; Run `python -m northgate`; 3) commands; 4) "Trace any number" walkthrough using `explain charge_capture` and the `source_line` column; 5) assumptions table; 6) what is counted vs not and why; 7) known limitations (row-average denial model; monthly aggregates; as-of date).
- When done, run everything from a fresh shell, paste the full `python -m northgate` output and `pytest -q` output in your final report, and list any number that did NOT match this spec (do not silently change the spec's numbers — if you believe one is wrong, report why).
