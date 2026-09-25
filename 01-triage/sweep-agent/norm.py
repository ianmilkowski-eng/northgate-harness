import re
PLACES="Fort Wayne's|Fort Wayne|Powell|Hilliard|Dublin|Ontario|Toledo|Nicholasville|Warsaw|Gahanna|Fishers|Perrysburg|Westerville|Carmel|Cincinnati|Mason|Auburn|Indianapolis|Worthington|Florence|Delaware|Mansfield|Lexington|Columbus"
NAMES="Priya|Renata|Josh|Odessa|Delphine|Marguerite|Bev|Dana|Nash|Dee|Tom|Wes|Curtis|Angela|Hollis|Idris|Clementine|Barrett|Sunniva|Amara|Osei"
DAYS="Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December|Thanksgiving"
NUMW="one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|first|second|third|fourth|fifth"
def norm(t):
    s=t
    s=re.sub(r'\b('+PLACES+r")(\b|'s)",'<P>',s,flags=re.I)
    s=re.sub(r'\b('+NAMES+r")('s)?\b",'<N>',s)
    s=re.sub(r'\b('+DAYS+r')\b','<D>',s)
    s=re.sub(r'\$?\d[\d,.]*%?','#',s)
    s=re.sub(r'\b('+NUMW+r')(-('+NUMW+r'))?\b','#',s,flags=re.I)
    s=re.sub(r"\b(?!I\b)[A-Z][A-Za-z'&.-]*",'<C>',s)
    s=re.sub(r'\s+',' ',s).strip().lower()
    return s
