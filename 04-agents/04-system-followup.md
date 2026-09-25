# Sub-agent 2, follow-up message (verbatim)

```
Follow-up changes to northgate-recovery. Thank you for flagging the rounding, the Patterson ambiguity and the triage miss. You were right on all three. Please implement the changes below, update README and tests, and make a NEW commit, with the same author and trailers as before: "Count Schein rebate, add FY2026 plan and deck numbers, fix triage quoting".

1. credential_hold: use the unrounded Delta paid ratio. That gives $165,040. Drop the 0.857 convention everywhere.

2. rebates: the counted run-rate becomes Henry Schein consolidated at 5.5% whole-amount, $165,206. It replaces Patterson's $150,187.
   - Reason: HS §7.2 explicitly says "entirety … not marginally". The Patterson summary is silent.
   - Keep both Patterson readings in metrics: whole-amount $150,187 and marginal $73,937.
   - Keep the Schedule A risk note. HS excluding NGD-17..22 is $1,053,090. The combined total without those sites is $2,094,464, which lands in the 4.0% tier.
   - FY2026 rebate capture: consolidate to HS effective 2026-03-01, using 2025 monthly volumes as the forecast. Jan–Feb stay at HS's 2025 split, and the agreement ends Oct 31. That gives calendar-2026 HS purchases of $2,224,732, at 4.0%, for $88,989.
   - One-time FY2025 claims:
     - HS Q4-2025: $10,148, deadline 2026-02-14.
     - Patterson FY2025, counted at the conservative marginal reading: 2.5% × (1,500,403.70 − 1,000,000) = $12,510. Show $37,510 as the whole-amount upper bound. Deadline 2026-03-01.
     - Counted total: $22,658.

3. Totals:
   - run_rate $1,330,073 (462,474 + 346,848 + 158,345 + 165,206 + 128,099 + 69,101)
   - one_time $349,629 (165,040 + 161,931 + 10,148 + 12,510)
   - Pre-tax with run-rate (illustrative): +$97,519

4. New northgate/plan.py and a `python -m northgate plan` command. Put every date and cost in assumptions.py, with source "Straterai delivery plan (assumption)".
   - Modules: exactly as in /home/claude/deck/deck-numbers.example.json → plan.modules.
   - FY2026 capture per finding: annual × months remaining in 2026 from the effective date / 12.
     - charge_capture, from 2026-03-01: $385,395
     - denial_priority, from 2026-04-01: $260,136
     - duplicate_plans, from 2026-04-01: $118,759
     - rebates: $88,989 (as above)
     - ghost_spend: NGD-23/24 from 2026-03-01 is $58,249. Halstead is $0 in FY2026: assume the Feb-2026 anniversary already auto-renewed, and that notice by Dec 2026 stops the Feb-2027 renewal. Total $58,249.
     - card_processing, from 2026-05-01: $46,067
     - fy2026_run_rate_capture $957,595; fy2026_total (plus one_time) $1,307,224
   - Cost, marked as an ESTIMATE to be replaced by a quote:
     - Build $120,000 (2 engineers × 10 weeks).
     - Run $1,500/month from 2026-03-02, so FY2026 run cost is $15,000.
     - fy2026_net $1,172,224.
     - Payback = 120,000 / (run_rate/52) = 4.69, displayed as 5 weeks.

5. New output file out/deck-numbers.json. It must match the schema of /home/claude/deck/deck-numbers.example.json exactly: same keys, same nesting, and the display-string rules in its _note.
   - Compute every value from the pipeline. Never copy from the example.
   - Map job_title "Revenue cycle management" to "Revenue Cycle Specialist" for display. hr/org-chart.txt says "(13) Revenue Cycle Specialists". Document the mapping.
   - method.signal_documents = a curated list of the 27 documents read in full: 4 transcripts, 9 emails, 3 contracts, 2 finance, 2 hr, 4 policies, 3 scanned invoices. Put the list in the code with one-line reasons.
   - Add a test that deck-numbers.json has the example's key structure. It should also check that the values equal the example's, except method.* and anything time-stamped.
   - If an example value is wrong, tell me. Don't bend the math to match it.

6. Triage fix. Quoted blocks in forwarded chains are currently skipped wholesale.
   - Split each quoted block: drop header lines (From/To/Sent/Subject/Date), keep the body.
   - Also mask any place name from practices.csv, plus Columbus and Dayton, at any position, including sentence-initial. That removes template false positives like "Florence had a patient complaint…".
   - Verify Bev's "I have been holding them rather than writing them off" now appears in triage output.
   - Report the new stats: utterances, words, rare lines, rare words, % reduction, documents with rare lines.

Another agent is concurrently building the deck at /home/claude/deck and will read out/deck-numbers.json. Don't touch /home/claude/deck.
```

**Outcome:** 227 tests pass. The agent also flagged three display strings in my contract that broke my own rounding rule, and a slide-wording risk: "ranked by dollars" was false once rebates rose above duplicate plans. I fixed the ranking in the next commit.
