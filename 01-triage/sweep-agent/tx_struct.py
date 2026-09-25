import os,re,datetime,collections
T='/home/claude/northgate/packet/documents/transcripts'
FLAGT={'2025-03-11-weekly-operations.txt','2025-05-20-it-integration-sync.txt','2025-06-04-rcm-team-review.txt','2025-09-17-lender-prep-internal.txt'}
utt=re.compile(r'^\[(\d\d):(\d\d):(\d\d)\] ([^:]+): (.*)$')
for f in sorted(os.listdir(T)):
    L=open(os.path.join(T,f)).read().split('\n')
    tag='[FLAGGED] ' if f in FLAGT else ''
    # header checks
    if L[0]!='NORTHGATE DENTAL PARTNERS': print(tag+f,'L1:',L[0])
    dl=[l for l in L[:8] if l.startswith('Date:')][0]
    d=datetime.datetime.strptime(dl[6:].strip(),'%B %d, %Y').date()
    if str(d)!=f[:10]: print(tag+f,'DATE MISMATCH',dl)
    rec=[l for l in L[:8] if l.startswith('Recorded')]
    if rec!=['Recorded via Zoom. Auto-transcribed. Not reviewed for accuracy.']: print(tag+f,'REC LINE',rec)
    pl=[l for l in L[:8] if l.startswith('Participants')][0]
    m=re.match(r'Participants \((\d+)\): (.*)',pl); n=int(m.group(1)); parts=[p.strip() for p in m.group(2).split(',')]
    if n!=len(parts): print(tag+f,'PARTICIPANT COUNT MISMATCH',pl)
    sep=[i for i,l in enumerate(L) if l.startswith('-----')]
    start=sep[0]+1
    speakers=collections.Counter(); prev=None; odd=[]
    for i,l in enumerate(L[start:],start):
        if not l.strip(): continue
        m=utt.match(l)
        if m:
            t=int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))
            if prev is not None and t<prev: odd.append(f'L{i+1} TIME BACKWARDS {l[:80]}')
            prev=t; speakers[m.group(4)]+=1
        elif l.startswith('    '): continue
        else: odd.append(f'L{i+1} NONSTANDARD: {l[:200]}')
    for s in speakers:
        if s not in parts: odd.append(f'SPEAKER NOT IN PARTICIPANTS: {s} ({speakers[s]} lines)')
    for p in parts:
        if p not in speakers: odd.append(f'PARTICIPANT NEVER SPEAKS: {p}')
    for o in odd: print(tag+f,'|',o)
