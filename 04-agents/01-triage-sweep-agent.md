# Sub-agent 1: independent sweep of the document corpus

**Role:** verify the de-templating filter. It reads everything the filter did *not* flag and reports any business content the filter missed.
**Type:** general-purpose sub-agent, run while the main session worked on the structured data.
**Result:** zero misses. It also found three things:

- A filler tell: every filler email is timestamped `00:00:00`.
- Eight "decoy" lines, each repeated 55–120 times.
- Four more transcripts that carry the "positional speaker labels" note.

That verification gave me enough confidence to stop reading filler. It did *not* catch the quoted-reply bug (see FAILURES.md, item 1), because it only looked at documents the filter hadn't flagged.

## Prompt (verbatim)

```
You are verifying a document-triage pass on a synthetic case-study packet (a fictional dental group, "Northgate Dental Partners"). The packet is at /home/claude/northgate/packet/documents/ (subfolders: transcripts/ 62 files, email/ 151 files, chat/ 14 files, contracts/, finance/, hr/, invoices/, policies/). Most of the corpus is deliberately generated filler (template lines like "Can we take that offline?", "Right. And just so it's on the record, that's the same thing we said last month about <place>", "<place> ran out of composite Tuesday", generic one-line emails like "Noted. I'll handle it.").

A de-templating filter already flagged these documents as containing real, non-boilerplate business content — do NOT spend time re-reading them:
- transcripts: 2025-03-11-weekly-operations.txt, 2025-05-20-it-integration-sync.txt, 2025-06-04-rcm-team-review.txt, 2025-09-17-lender-prep-internal.txt
- email: 2025-04-09-merchant-statements.txt, 2025-06-27-re-recovery-by-person.txt, 2025-07-22-supply-agreement-question.txt, 2025-08-19-carrier-invoice-headcount.txt, 2025-09-30-the-columbus-office.txt, 2025-10-01-re-the-columbus-office.txt, 2025-10-14-re-two-cost-centers.txt, 2025-10-14-two-cost-centers-i-dont-recognize.txt, 2025-11-06-fw-fw-fw-toledo-question.txt
- all of contracts/, finance/, hr/, policies/, and invoices/*SCANNED*.txt

YOUR JOB: find anything the filter MISSED. Specifically:
1. Read every OTHER email in email/ in full (they are short; use bash loops to print many at once). Flag any email whose body, quoted chain, subject, sender, or dates carry business-relevant facts (money, vendors, contracts, headcount, credentialing, claims, billing, benefits, supplies, leases, software, decisions or reversals of decisions) rather than generic filler. Note anything odd in headers too (wrong dates, out-of-order chains, a sender whose title doesn't match).
2. For chat/ and the remaining transcripts/: do not read line by line. Instead write short Python to normalize each line (mask place names/capitalized words and numbers) and list any line whose normalized form occurs fewer than 4 times across the whole corpus, plus any line mentioning dollar amounts, a vendor name, 'NGD-', 'rebate', 'credential', 'Delta', 'Anthem', 'Osei', 'Vance', 'Marguerite', 'lease', 'Grandview', 'Beavercreek', 'Dayton', 'Halstead', 'true-up', 'license', 'routing slip', 'write-off', 'timely', 'processor', 'CardConnect', 'BluePay', 'Sunbit'. Also check the filler invoices (invoices/filler-*.txt) for anything unusual (odd cost centers, vendors, amounts).
3. Check transcript headers (participants lists, meeting titles, dates) for anomalies, e.g. a participant who couldn't have been there, a meeting whose date is out of order with its sequence number, or '[Transcription note' lines.

Report back concisely: a list of every document with genuinely business-relevant content NOT already in the list above (file path + 1-3 sentence summary + the exact quote), plus any anomalies. If you find nothing beyond the list, say so plainly and state what you checked and how. Do not speculate; quote the text. Keep the report under 800 words.
```

The scripts it wrote are in `../01-triage/sweep-agent/`.
