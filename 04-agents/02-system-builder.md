# Sub-agent 2: system builder

**Role:** turn my reference script (`02-analysis/findings_v0.py`) and the spec (`03-specs/SYSTEM-SPEC.md`) into the client-grade repo `northgate-recovery`. It adds row-level evidence, a CLI, tests and a README.

**How it ran:** in parallel with sub-agent 3 (glass kit), so I could keep working on the design.

**The spec was written as a contract.** It pins every expected number, so the agent reproduces my math and doesn't re-derive it. The agent is also told to *report* any number it thinks is wrong rather than change it. That clause was the most valuable line in the prompt, because it pushed back three times:

- **The Delta paid ratio.** The spec rounded it to 0.857 before multiplying. The agent flagged the $55 difference.
- **The Patterson rebate.** The contract summary never says whether the rate applies to the whole amount or only the portion above each tier. On the marginal reading the steady-state figure is $73,937, not $150,187.
- **"Lowest on-site hours in the company."** False. Marguerite Vance is the lowest of the 171 *full-time* staff; 59 part-timers log fewer hours.

## Prompt (verbatim)

```
Build the Python system repo described in /home/claude/northgate-recovery/SPEC.md, inside /home/claude/northgate-recovery/. Read SPEC.md fully first, then read the two reference scripts in that folder (findings_v0.py, detemplate.py) and skim packet/README.md, packet/northgate-overview.md and packet/appendix-contracts-and-constraints.md for context. The data is in packet/data/*.csv and the documents in packet/documents/.

This is a take-home for a Forward Deployed Engineer role: graders will clone the repo on a clean machine, run one install command and one run command, and then poke at the numbers. The numbers in SPEC.md are the numbers that will appear in the client deck, so they must be reproduced exactly (to the dollar after rounding). If you believe a spec number is wrong, do not silently change it: keep the spec's method, and report the discrepancy with your reasoning in your final message.

Requirements recap (SPEC.md is authoritative):
- Package `northgate/` with the CLI `python -m northgate` [run|explain <id>|list|tieouts|triage] and `--as-of` (default 2026-02-02), `--packet`, `--out`.
- Every finding writes an evidence CSV with `source_file` and `source_line` (original CSV line number, header = line 1) so any number can be traced to rows.
- assumptions.py holds every constant with its source document path and a VERBATIM quote; tests/test_quotes.py must verify each quote appears verbatim in the file (OCR typos included — copy exactly from the file; use short distinctive quotes).
- out/findings.json in the schema in SPEC.md, including the `metrics` blocks the deck will chart.
- tests/test_numbers.py asserts all expected values from SPEC.md.
- Clean, professional code (type hints, docstrings, small functions, no magic numbers outside assumptions.py). Plain-text terminal report, nicely aligned, no colour libraries. Only runtime dependency: pandas.
- README.md as specified. Write it plainly and precisely, like a senior engineer handing a tool to a client's finance team: no hype, no emoji.
- Initialise a git repo and make one commit.

Verify from a fresh shell: pip install -r requirements.txt && python -m northgate && python -m northgate explain charge_capture && python -m northgate tieouts && python -m pytest -q

Final message: paste the full `python -m northgate` output, the `pytest -q` summary line, the repo tree, and a short list of anything that did not match SPEC.md or that you think a skeptical CFO would attack.
```

(Abridged only where it repeated SPEC.md.)

## Follow-up (after the first build)

The follow-up told it to:

- Count Henry Schein at 5.5% of the whole amount. The contract states that explicitly; Patterson's is silent.
- Book Patterson's 2025 claim on the conservative marginal reading.
- Use the unrounded Delta ratio.
- Add `plan.py` (FY2026 cash by module go-live).
- Write `out/deck-numbers.json`, a JSON contract that the deck renders from.
- Fix the triage bug it had spotted (FAILURES.md, item 1).

The full text is in `04-system-followup.md`.
