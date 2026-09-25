"""De-templating filter: surfaces the rare, non-boilerplate utterances in the document corpus.
Every utterance is reduced to a 'skeleton' (capitalized words -> <C>, digits -> <N>).
Boilerplate generated from templates collapses onto a few skeletons; planted signal is unique."""
import re, os, glob, collections, json, sys
ROOT = "/home/claude/northgate/packet/documents"

def skel(t):
    t = re.sub(r"\s+", " ", t.strip())
    words = t.split(" ")
    out = []
    for i, w in enumerate(words):
        if re.search(r"\d", w): out.append("<N>")
        elif i > 0 and w[:1].isupper() and w not in ("I", "I'm", "I'll", "I've", "I'd"): out.append("<C>")
        else: out.append(w.lower())
    s = " ".join(out)
    s = re.sub(r"(<C> ?)+", "<C> ", s)
    return s.strip()

utts = []  # (source, date/time, speaker, text)
# transcripts: merge continuation lines
for f in sorted(glob.glob(f"{ROOT}/transcripts/*.txt")):
    cur = None
    for line in open(f, encoding="utf-8"):
        m = re.match(r"^\[(\d\d:\d\d:\d\d)\] ([^:]+): (.*)$", line.rstrip("\n"))
        if m:
            if cur: utts.append(cur)
            cur = [os.path.relpath(f, ROOT), m.group(1), m.group(2), m.group(3)]
        elif line.startswith("    ") and cur:
            cur[3] += " " + line.strip()
        else:
            if cur: utts.append(cur); cur = None
            if line.strip() and not line.startswith(("NORTHGATE", "Date:", "Recorded", "Participants", "----")) and not re.match(r"^\[\d", line):
                utts.append([os.path.relpath(f, ROOT), "", "_note", line.strip()])
    if cur: utts.append(cur)
# chats
for f in sorted(glob.glob(f"{ROOT}/chat/*.txt")):
    for line in open(f, encoding="utf-8"):
        m = re.match(r"^\[([\d\- :]+)\] ([^:]+): (.*)$", line.rstrip("\n"))
        if m: utts.append([os.path.relpath(f, ROOT), m.group(1), m.group(2), m.group(3)])
# emails: body paragraphs (excluding signature/disclaimer/headers)
for f in sorted(glob.glob(f"{ROOT}/email/*.txt")):
    txt = open(f, encoding="utf-8").read()
    txt = txt.split("\n---\n")[0]
    paras = re.split(r"\n\s*\n", txt)
    for p in paras:
        p2 = "\n".join(l.lstrip("> ").rstrip() for l in p.splitlines())
        if re.match(r"^(From|To|Sent|Subject):", p2) or "northgatedental.com" in p2: continue
        p2 = re.sub(r"^(From|Sent|Subject):.*$", "", p2, flags=re.M).strip()
        if not p2 or len(p2.split()) <= 1: continue
        utts.append([os.path.relpath(f, ROOT), "", "", re.sub(r"\s+", " ", p2)])

cnt = collections.Counter(skel(u[3]) for u in utts)
total_words = sum(len(u[3].split()) for u in utts)
rare = [u for u in utts if cnt[skel(u[3])] <= 2 and len(u[3].split()) >= 12]
print(f"utterances={len(utts)} words={total_words} distinct_skeletons={len(cnt)} rare_long={len(rare)} rare_words={sum(len(u[3].split()) for u in rare)}", file=sys.stderr)
json.dump(rare, open("/home/claude/work/rare_utterances.json", "w"), indent=0)
by_src = collections.defaultdict(list)
for u in rare: by_src[u[0]].append(u)
for src in sorted(by_src):
    print(f"\n##### {src}")
    for u in by_src[src]:
        print(f"[{u[1]}] {u[2]}: {u[3]}")
