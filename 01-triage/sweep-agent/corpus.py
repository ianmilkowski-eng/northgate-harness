import os,re,collections
B='/home/claude/northgate/packet/documents'
FLAGT={'2025-03-11-weekly-operations.txt','2025-05-20-it-integration-sync.txt','2025-06-04-rcm-team-review.txt','2025-09-17-lender-prep-internal.txt'}
utt=re.compile(r'^\[(\d\d:\d\d:\d\d)\] ([^:]+): (.*)$')
cpat=re.compile(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d)\] ([^:]+): (.*)$')
def load():
    recs=[]  # (src, file, lineno, speaker, text)
    for f in sorted(os.listdir(B+'/transcripts')):
        L=open(B+'/transcripts/'+f).read().split('\n')
        start=[i for i,l in enumerate(L) if l.startswith('-----')][0]+1
        cur=None
        for i,l in enumerate(L[start:],start):
            m=utt.match(l)
            if m:
                if cur: recs.append(cur)
                cur=['T',f,i+1,m.group(2),m.group(3)]
            elif l.startswith('    ') and cur:
                cur[4]+=' '+l.strip()
            else:
                if cur: recs.append(cur); cur=None
        if cur: recs.append(cur)
    for f in sorted(os.listdir(B+'/chat')):
        L=open(B+'/chat/'+f).read().split('\n')
        for i,l in enumerate(L):
            m=cpat.match(l)
            if m: recs.append(['C',f,i+1,m.group(2),m.group(3)])
    return recs
