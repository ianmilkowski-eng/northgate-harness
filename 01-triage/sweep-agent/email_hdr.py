import os, re, collections, datetime
D='/home/claude/northgate/packet/documents/email'
FLAG=set("""2025-04-09-merchant-statements.txt 2025-06-27-re-recovery-by-person.txt 2025-07-22-supply-agreement-question.txt 2025-08-19-carrier-invoice-headcount.txt 2025-09-30-the-columbus-office.txt 2025-10-01-re-the-columbus-office.txt 2025-10-14-re-two-cost-centers.txt 2025-10-14-two-cost-centers-i-dont-recognize.txt 2025-11-06-fw-fw-fw-toledo-question.txt""".split())
def pd(s): return datetime.datetime.strptime(s.strip(), '%a, %d %b %Y %H:%M:%S %z')
titles=collections.defaultdict(collections.Counter)
people=collections.Counter()
issues=[]
tz=collections.Counter(); times=collections.Counter()
for f in sorted(os.listdir(D)):
    txt=open(os.path.join(D,f)).read()
    body=txt.split('\n---\n')[0]
    L=body.split('\n')
    h={}
    for l in L[:4]:
        k,v=l.split(':',1); h[k]=v.strip()
    m=re.match(r'(.+?) <(.+?)>',h['From']); fname,femail=m.group(1),m.group(2)
    people[fname]+=1
    tos=re.findall(r'([^,<]+?) <([^>]+)>',h['To'])
    for n,e in tos: people[n.strip()]+=1
    if fname in [n.strip() for n,e in tos]: issues.append((f,'sender also in To'))
    # email address consistency with name
    for n,e in [(fname,femail)]+[(n.strip(),e) for n,e in tos]:
        parts=n.replace('Dr. ','').split()
        exp=(parts[0][0]+parts[-1]).lower()+'@northgatedental.com'
        if e!=exp: issues.append((f,f'address {e} for {n} (expected {exp})'))
    # signature block: find line equal to fname (full name) after Subject
    try:
        i=L.index(fname,4)
        title=L[i+1]; comp=L[i+2]; sigmail=L[i+3]
        titles[fname][title]+=1
        if comp!='Northgate Dental Partners': issues.append((f,'company line: '+comp))
        if sigmail!=femail: issues.append((f,f'sig email {sigmail} != from {femail}'))
    except ValueError:
        issues.append((f,'no signature full-name line matching From'))
    # sent vs filename
    sd=pd(h['Sent']); tz[h['Sent'][-5:]]+=1; times[h['Sent'].split()[4]]+=1
    fd=f[:10]
    if sd.strftime('%Y-%m-%d')!=fd: issues.append((f,f'Sent {sd.date()} != filename {fd}'))
    if sd.strftime('%a')!=h['Sent'][:3]: issues.append((f,'weekday mismatch '+h['Sent']))
    # quoted
    qs=re.findall(r'> From: (.+)\n> Sent: (.+)\n',body)
    for n,s in qs:
        people[n.strip()]+=1
        q=pd(s)
        if q.strftime('%a')!=s.strip()[:3]: issues.append((f,'quoted weekday mismatch '+s))
        if q>sd: issues.append((f,f'quoted msg from {n} dated {q.date()} AFTER top Sent {sd.date()}'))
        if (sd-q).days>30: issues.append((f,f'quoted msg {q.date()} >30d before Sent {sd.date()}'))
print("TZ:",tz); print("Times:",times)
print("\n=== titles per sender (from signature) ===")
for p,c in sorted(titles.items()): print(p, dict(c))
print("\n=== all people seen ===")
for p,c in sorted(people.items()): print(c,p)
print("\n=== issues ===")
for f,i in issues: print(('[FLAGGED] ' if f in FLAG else '')+f,'|',i)
