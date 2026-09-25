import os, re, collections, datetime
D='/home/claude/northgate/packet/documents/email'
FLAG=set("""2025-04-09-merchant-statements.txt 2025-06-27-re-recovery-by-person.txt 2025-07-22-supply-agreement-question.txt 2025-08-19-carrier-invoice-headcount.txt 2025-09-30-the-columbus-office.txt 2025-10-01-re-the-columbus-office.txt 2025-10-14-re-two-cost-centers.txt 2025-10-14-two-cost-centers-i-dont-recognize.txt 2025-11-06-fw-fw-fw-toledo-question.txt""".split())
def parse_date(s):
    return datetime.datetime.strptime(s.strip(), '%a, %d %b %Y %H:%M:%S %z')
emails={}
for f in sorted(os.listdir(D)):
    txt=open(os.path.join(D,f)).read()
    body=txt.split('\n---\n')[0]
    lines=body.split('\n')
    h={}
    for l in lines[:4]:
        k,v=l.split(':',1); h[k]=v.strip()
    emails[f]=(h,lines,txt)
# 1) line frequency across all emails (body + quoted), masked
def norm(l):
    l=re.sub(r'\b\d+(st|nd|rd|th)?\b','#',l)
    l=re.sub(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|next week|the #)\b','<DAY>',l)
    l=re.sub(r"\b[A-Z][a-zA-Z'.-]*( [A-Z][a-zA-Z'.-]*)*",'<Cap>',l)
    return l.strip()
cnt=collections.Counter(); where=collections.defaultdict(list)
for f,(h,lines,txt) in emails.items():
    for i,l in enumerate(lines):
        if i<4: continue
        s=l.strip()
        if not s or s=='>' : continue
        if s.startswith('> From:') or s.startswith('> Sent:'): continue
        s=s.lstrip('> ').strip()
        if not s: continue
        n=norm(s); cnt[n]+=1; where[n].append((f,s))
print("=== distinct normalized content lines (count, example) ===")
for n,c in sorted(cnt.items(), key=lambda x:x[1]):
    fl=[w for w in where[n] if w[0] not in FLAG]
    if c<4 or len(fl)<len(where[n]):
        pass
    print(c, '|', n[:110], '| unflagged:', len(fl))
