import json, re, collections, sys
sys.argv=['x']
exec(open('detemplate.py').read().split("cnt = collections.Counter")[0])
# improved skeleton: also mask a leading capitalized place-like token and possessives
def skel2(t):
    s = skel(t)
    s = re.sub(r"^[a-z]+'s ", "<C>'s ", s)  # "gahanna's pan" -> "<C>'s pan"
    s = re.sub(r"^(\w+) (had|lost|ran|is|has|wants|was|needs) ", r"<C> \2 ", s)
    return s
cnt = collections.Counter(skel2(u[3]) for u in utts)
# print frequency distribution of chats
chat = [u for u in utts if u[0].startswith("chat/")]
cc = collections.Counter(skel2(u[3]) for u in chat)
print("chat utterances", len(chat), "distinct", len(cc))
rare_chat = [u for u in chat if cnt[skel2(u[3])] <= 3]
print("rare chat lines:", len(rare_chat))
for u in rare_chat: print(f"  {u[0]} [{u[1]}] {u[2]}: {u[3]}")
# transcripts: rare lines of any length that weren't in the >=12 word list
tr = [u for u in utts if u[0].startswith("transcripts/") and cnt[skel2(u[3])] <= 3 and len(u[3].split()) < 12]
print("\nshort rare transcript lines:", len(tr))
for u in tr: print(f"  {u[0]} [{u[1]}] {u[2]}: {u[3]}")
em = [u for u in utts if u[0].startswith("email/") and cnt[skel2(u[3])] <= 3 and len(u[3].split()) < 12]
print("\nshort rare email paras:", len(em))
for u in em: print(f"  {u[0]}: {u[3]}")
# top skeletons for reference
print("\nTop 15 skeletons:")
for s,c in cnt.most_common(15): print(c, s)
