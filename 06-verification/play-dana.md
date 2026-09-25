# The adversarial pass: an agent playing Dana

Stage 3 is Charlie or James playing Dana, and "Dana's job is to disbelieve you". So I ran that meeting early, with an agent whose only job was to break the numbers.

## Setup

The agent works from fresh context. It had read-only access to:
- the packet
- the deck PDF
- the system repo

The order was fixed:
1. Re-derive every headline number from raw CSVs *before* reading my code, so it can't inherit my mistakes.
2. Check that every number in the PDF traces to the system output.
3. Attack the logic.
4. Fact-check every quote.
5. Look for missed money.

## Prompt (verbatim, lightly trimmed)

```
You are playing Dana Reyes, the CFO of Northgate Dental Partners, plus her most skeptical analyst. A consultant is about to present a deck claiming $1.33M/yr of recoverable value, plus $350K one-time. You already paid $85K once for a consulting deck that told you nothing. Your job is to BREAK these numbers before the meeting, so the consultant can fix what's wrong. Be adversarial but fair: a finding that survives your attack is a finding.

Tasks, in this order:
1. INDEPENDENT RE-DERIVATION FIRST. Before reading the consultant's code, write your own pandas code against packet/data to re-derive each headline figure...
2. DECK == SYSTEM. Every number printed in the PDF must be traceable to `python -m northgate` output or out/deck-numbers.json...
3. ATTACK THE LOGIC. For each finding: double counting between findings; wrong application of the 78% collection or 72% margin; appendix constraints that block or shrink the finding; data caveats; timing and contract assumptions; whether "sites that never opened" is actually supported; anything that touches the off-the-table list in appendix §8.
4. FACT-CHECK THE COPY...
5. MISSED MONEY (be conservative)...

Output: a ranked list of issues (would lose the room / should fix / nitpick) with evidence and a concrete fix; a table of your independent re-derivations vs the deck; the 6 hardest questions Dana will ask, each with the best one-line answer the data supports.
```

## What it found

**Every number re-derived exactly from raw rows.** No double counting between findings, and deck == system. Two findings still would have lost the room:

1. **The denial model assumed capacity is free.** It lost "the same 5,033 claims" under value-first ordering. But in the worklog, people who work bigger claims take more touches per claim.
2. **The rebate ignored Schedule A.** Schein only pools locations on its Schedule A, and the six sites bought after the agreement may not be on it.

It also caught:
- Dr. Osei's claims start expiring March 14, before the software that was supposed to rebill them goes live.
- 16 provider-payer credentials are already past their recredential date, one of them Medicaid (no retro billing). That's the same setup as the Osei lapse.
- "Sites that never opened" is stronger than the evidence. The IT manager thought they opened in 2023.

## What changed because of it

| Finding | Before | After |
|---|---|---|
| Denial queue | $347K | **$203K** counted, range $107K–$347K |
| Rebates | $165K | **$74K** floor, up to $165K |
| One-time | $350K | **$318K**: the backlog is now valued at go-live, not today |
| Headline | $1.33M | **$1.10M** counted, up to $1.33M |

- **Denial queue:** counted with effort rising for bigger claims.
- **Rebates:** Patterson's marginal reading is counted, and the Schedule A and item-price questions are on the slide.
- The Osei rebill and a credential sweep moved into week 0, before any software exists.

## A second opinion on the first opinion

When the system agent implemented the effort-adjusted model, it pointed out something important. The effort slope comes from differences *between people*: the two queue specialists work cheap claims fast. *Within* one person's months, the slope is flat. So "bigger claims take more work" isn't proven either.

I kept the cautious number as the counted floor and put the full range on the slide. The first month of the ranked queue measures the real effort curve. That's the honest version: I don't know the slope, the data doesn't know it, and the pilot finds out.

## The questions Dana will ask in Stage 3

These are the reviewer's six hardest questions. Each answer is what the data supports *after* the revisions.

1. **"Why would value-first ordering lose the same number of claims if big claims take more work?"**
   It might not. That's why the counted number is the cautious $203K, not $347K. Within one person's work, the data shows no effort slope. The ranked queue's first month measures it.
2. **"Are Wabash and Stonebridge on Schein's Schedule A?"**
   We don't know. The floor ($74K) doesn't depend on it. For 2026 we'd move volume to Patterson, which has no Schedule A clause, and rebid both at renewal.
3. **"How much of the $1.10M is measured, not modeled?"**
   $818K. That's unbilled procedures, duplicate plans, ghost spend and card fees. Denials ($203K) are modeled. Rebates ($74K) are contractual, at the floor.
4. **"What does a month's delay cost?"**
   The $10K Schein claim (Feb 14) and the Patterson claim (Mar 1). About $1,200 a day of unbilled backlog. And Dr. Osei's claims start expiring Mar 14.
5. **"Can we get back what we already paid on the sellers' plans?"**
   Maybe. It's the sellers' obligation under the purchase agreements, and FY2025 alone was $158K. That's counsel's call, and it isn't counted.
6. **"Isn't your $1.94M backfill just Grantley again?"**
   That's why it isn't counted. If managers already fill 20% of openings, it's about $969K. Nothing counts until a 3-site pilot measures the fill rate.
