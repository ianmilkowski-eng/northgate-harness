# Northgate harness

This is how I built the Northgate submission: the scripts, the specs, the sub-agent prompts, and what broke along the way. The system itself lives in the other repo (`northgate-recovery`). This one is about how it got made.

## The setup

- **Main session:** Claude (Cowork). It orchestrates, does the data analysis, and makes the calls.
- **Sub-agents** for anything that could run in parallel or needed fresh eyes:
  - a document sweep that checked my filter
  - a system builder
  - a design R&D agent for the glass rendering, which later built the deck
  - an adversarial reviewer playing Dana
- **Skills:** a data-viz skill for chart rules and a palette validator, and a design skill for layout and type.
- **Connectors:** Google Drive and Chrome. I pulled up my own past decks to set the visual direction before any slide got designed.

No custom infrastructure. The harness is the workflow: specs that pin numbers, agents that have to report disagreements, and a JSON contract between the system and the deck.

## How I got through 259,000 words

This was the most interesting problem in the packet.

**What I tried first.** I read the files. After two transcripts it was obvious that wouldn't scale. Almost every line is one of a few dozen template sentences with a different town swapped in: "Can we take that offline?", "Florence ran out of composite Tuesday", "Noted. I'll handle it." Keyword search didn't help either. Search for "Delta" and you get twenty copies of "who has the login for the Delta portal".

**What worked: throw away the repetition.** `01-triage/detemplate_v0.py` reduces every utterance to a skeleton. Capitalized words become `<C>`, digits become `<N>`, and a place name becomes a placeholder. Then it counts how often each skeleton appears across the whole corpus. Template lines collapse onto a few hundred skeletons, and real sentences are unique.

- **v0:** 15,639 utterances and 182K words down to 78 rare lines, 1,942 words.
- **v1:** after the fixes below, 1,757 words.

What survived pointed at 13 conversations. Add the 14 contracts, policies, HR, finance docs and scanned invoices, and that's 27 documents. I read all 27 in full.

**Checking the filter.** A filter that throws away 99% of the text needs its own check. So a sub-agent read everything the filter *dropped*: all 142 unflagged emails in full, plus a separate normalization of every chat and transcript line. It found nothing I'd missed. It also found some tells:
- Every filler email is stamped `00:00:00`.
- Eight serious-sounding decoy lines, like "three different codes for the same buildup", are each repeated 55 to 120 times. Citing one would've been a mistake. The prompt and its scripts are in `04-agents/01-triage-sweep-agent.md` and `01-triage/sweep-agent/`.

**What the filter missed, and how I caught it.** v0 threw away quoted replies inside forwarded email chains. One of those replies was Bev saying she'd been *holding* Dr. Osei's denied Delta claims instead of writing them off. That's the only evidence $165K is still recoverable. I caught it because I read the flagged documents in full and didn't trust the extracted lines. The system agent then noticed the quote wasn't in the triage output. Details are in `FAILURES.md`.

**Joining sentences to columns.** Every finding that matters sits where a document and a CSV meet:
- Tom's "nobody checks what got done vs what got billed" meets `procedures-monthly.csv`, with a 2 to 6% gap at exactly his 8 sites.
- Dee's "two sellers never cancelled their plans" meets `benefits-enrollment.csv`, which shows four.
- Josh's "we consolidated everything to Schein" meets a 50/50 purchase split every single month.

Each join is written down in `02-analysis/analysis-notes.md`.

## From analysis to deck, without retyping a number

1. `02-analysis/findings_v0.py`: my first pass, one script, every number.
2. `03-specs/SYSTEM-SPEC.md`: a spec that pins every expected value. The system agent had to reproduce them to the dollar and *report* any it thought were wrong, instead of changing them. That one instruction caught three real mistakes.
3. **The system repo:** a CLI, evidence CSVs with source line numbers, and tests.
4. `03-specs/deck-numbers.contract.json`: the only thing the deck is allowed to read. The system writes it, and a test checks its shape.
5. `05-deck/build.py`: renders all 15 slides from that JSON and exports the PDF. When my deck spec asked for a number that wasn't in the contract, the agent rewrote the sentence instead of typing the number.

## The adversarial pass

Before calling it done, I had an agent play Dana and try to break every number (`06-verification/play-dana.md`). Everything re-derived exactly. Two findings didn't survive the logic:

- The denial model assumed a big claim takes the same work as a small one.
- The rebate ignored a Schedule A clause in the Schein contract.

Both went down. The headline went from $1.33M to $1.10M counted, and I'd rather walk into Stage 3 with that.

## Layout

| Folder | What's in it |
|---|---|
| `01-triage/` | The skeleton filter (v0 and the short-line pass), its v0 output, and the sweep agent's scripts |
| `02-analysis/` | My first-pass script and the running analysis notes |
| `03-specs/` | The system spec, the deck spec, and the JSON contract between them |
| `04-agents/` | Every sub-agent prompt, verbatim, with what each one got right and wrong |
| `05-deck/` | The deck builder and the glass kit (`NOTES.md` has the PDF rendering tests) |
| `06-verification/` | The play-Dana prompt, what it found, and what changed |
| `FAILURES.md` | Ten things that broke and how each one got caught |

## What I stripped

Nothing proprietary is in here. Left out: the packet itself (it's in the system repo) and rendering intermediates (screenshots and plates).
