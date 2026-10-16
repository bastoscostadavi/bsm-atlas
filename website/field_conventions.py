"""Conservative, exact conventions for the small gauge/matter catalogue.

No source claims are edited. Missing/non-unique representation labels stay
unresolved. A fixed Dynkin-node convention, not dimension alone, is the key.
"""
from fractions import Fraction
from functools import reduce
from math import gcd, lcm, comb
import re

SM = [("su(3)","colour"),("su(2)","weak_L"),("u(1)","hypercharge")]
EW = SM[1:]
PATTERN = re.compile(r"(?:SU|SO|Spin|Sp|O|U)\([^()]+\)")
TRANS = str.maketrans({"−":"-","–":"-","⁄":"/"})


def rational(value):
    text=str(value if value is not None else "").translate(TRANS).strip().replace(" ","")
    return Fraction(text) if re.fullmatch(r"[+-]?\d+(?:/[+-]?\d+)?",text) else None


def primitive_scale(values):
    values=[v for v in values if v]
    if not values: return None
    denominator=lcm(*(v.denominator for v in values))
    return Fraction(denominator,reduce(gcd,(abs(int(v*denominator)) for v in values)))


def factor(label,role=""):
    """Canonical compact Lie algebra IDs; group/global form is not inferred."""
    text=label.lower().replace("spin(","so(")
    m=re.fullmatch(r"(su|so|sp|o|u)\(([^)]+)\)",text)
    if not m: return {"id":"unknown","label":"?","role":role,"type":"unknown","rank":None}
    family,n=m.groups()
    if family=="o": family="so"  # same Lie algebra, not the same global group.
    if family=="u" and n=="1": return {"id":"u1","label":"u(1)","role":role,"type":"U1","rank":1}
    if not n.isdigit(): return {"id":family+"("+n+")","label":family+"("+n+")","role":role,"type":"parameterized","rank":None}
    n=int(n)
    if family=="su": typ,rank="A",n-1
    elif family=="so": typ,rank=("D",n//2) if n%2==0 else ("B",(n-1)//2)
    elif family=="sp":
        # Source Sp(Nc) is parameterized in this corpus. Never guess whether a
        # numeric source Sp(N) uses rank or fundamental-dimension convention.
        return {"id":"sp-source("+str(n)+")","label":"sp("+str(n)+")","role":role,"type":"unresolved_sp_convention","rank":None}
    else: return {"id":"unknown","label":"?","role":role,"type":"unknown","rank":None}
    aliases={( "B",1):("A",1),("D",3):("A",3),("B",2):("C",2)}
    typ,rank=aliases.get((typ,rank),(typ,rank))
    canonical={"A":"su("+str(rank+1)+")","B":"so("+str(2*rank+1)+")","C":"sp_rank("+str(rank)+")","D":"so("+str(2*rank)+")"}[typ]
    return {"id":typ+str(rank),"label":canonical,"role":role,"type":typ,"rank":rank}


def gauge_factors(label):
    text=label or ""
    if text=="SM_A × SM_B" or text.startswith("(SU(3)c × SU(2) × U(1))_A"):
        return [factor(f,r+"_"+copy) for copy in ["A","B"] for f,r in [(x.upper(),r) for x,r in SM]]
    if text.startswith("[SU(3) × SU(2)]_A"):
        return [factor(f,r+"_"+copy) for copy in ["A","B"] for f,r in [(x.upper(),r) for x,r in SM[:2]]]
    if text.startswith("[SU(2) × U(1)]1"):
        return [factor(f,r+"_"+copy) for copy in ["1","2"] for f,r in [(x.upper(),r) for x,r in EW]]
    if text=="Electroweak gauge group acting identically on the three Higgs doublets": return [factor(f.upper(),r) for f,r in EW]
    matches=list(PATTERN.finditer(text))
    result=[]
    for i,m in enumerate(matches):
        suffix=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].split("×")[0].split(";")[0].strip(" _")
        role={"c":"colour","C":"colour","colour,":"colour","color":"colour","L":"left","R":"right","Y":"hypercharge","Y sector of the inherited Standard Model":"hypercharge","Y within the inherited Standard Model":"hypercharge"}.get(suffix,suffix)
        if len(role)>18 or not role: role="factor_"+str(i+1)
        result.append(factor(m.group(),role))
    sm_context=any(x in text for x in ["Standard Model gauge", "MSSM gauge", "Inherited SM gauge sector"])
    if sm_context and not text.startswith(("Electroweak","SU(2)")) and not (any(f["id"]=="A2" for f in result) and any(f["id"]=="A1" for f in result)):
        result=[factor(f.upper(),r) for f,r in SM]+result
    if not result and text.startswith("Ordinary color"): result=[factor("SU(3)","colour")]
    if [f["id"] for f in result]==["A2","A1","u1"]: result=[factor(f.upper(),r) for f,r in SM]
    if [f["id"] for f in result]==["A1","u1"]: result=[factor(f.upper(),r) for f,r in EW]
    return result


def conjugate(label):
    if label in {"1","2","3"}: return "bar("+label+")" if label=="3" else label
    return label[4:-1] if label.startswith("bar(") else "bar("+label+")"


def irrep_token(value):
    text=str(value or "").strip().translate(TRANS)
    names={"trivial":"1","singlet":"1","doublet":"2","triplet":"3","octet":"8","adjoint octet":"8","adjoint":"Adj","fundamental":"Fund","antifundamental":"bar(Fund)"}
    if text in names: return names[text]
    m=re.match(r"^(?:bar(\d+)|(\d+)(?:-bar|̄|\*|bar))",text)
    if m: return "bar("+(m.group(1) or m.group(2))+")"
    m=re.fullmatch(r"(\d+)(?:L|R)?",text)
    return m.group(1) if m else None


def dynkin(algebra,label):
    """Only unambiguous identifications; no dimension-only guessing in D/E."""
    rank=algebra.get("rank");typ=algebra.get("type")
    if not rank or typ in {"U1","unknown"}: return None
    if label=="1": return [0]*rank
    if typ=="A":
        n=rank+1
        if rank==1 and label.isdigit(): return [int(label)-1]
        if label in {str(n),"Fund"}: return [1]+[0]*(rank-1)
        if label in {"bar("+str(n)+")","bar(Fund)"}: return [0]*(rank-1)+[1]
        if label in {str(n*n-1),"Adj"}: return [1]+[0]*(rank-2)+[1] if rank>1 else [2]
        # Explicitly retained familiar SU(3) tensor representations.
        if rank==2:
            known={"6":[2,0],"bar(6)":[0,2],"10":[3,0],"bar(10)":[0,3]}
            return known.get(label)
    return None


def parse_tuple(row,factors,override=None):
    if override: return override["values"],"curated_source_statement"
    text=(row.get("representation_label") or "").translate(TRANS).strip()
    if text.startswith("trivial"): return ["0" if f["type"]=="U1" else "1" for f in factors],"trivial_representation"
    if len(factors)==1:
        return ([row.get("exact_charge")],"source_charge") if factors[0]["type"]=="U1" else ([text.split(",")[0]],"source_irrep")
    if " + " in text or "with conjugate" in text: return None,"collection_or_direct_sum_not_flattened"
    m=re.search(r"\(([^()]+)\)(?:_?\(?([+-]?\d+(?:/\d+)?)\)?)?",text)
    if m:
        values=[v.strip() for v in re.split(r"[,;]",m.group(1))]
        if m.group(2) is not None: values.append(m.group(2))
        if len(values)==len(factors):
            if "Direct sum" in text:
                vector=re.search(r",\s*F[^=]*=\(([^()]+)\)\s*$",text)
                if vector and factors[-1]["type"]=="U1": values[-1]="["+vector.group(1)+"]"
            return values,"indexed_family_tuple" if "Direct sum" in text else "source_tuple"
    if len(factors)==2 and factors[-1]["type"]=="U1":
        m=re.fullmatch(r"(\d+\*?)_\(?([+-]?\d+(?:/\d+)?)\)?",text)
        if m: return list(m.groups()),"source_subscript"
    return None,"unconverted_source_expression"


def dimension_a(labels):
    """Weyl dimension formula for A_r; exact integer arithmetic."""
    if labels is None: return None
    n=len(labels)+1
    value=Fraction(1)
    for i in range(n):
        for j in range(i+1,n): value*=Fraction(sum(labels[i:j])+j-i,j-i)
    return int(value)


def young_rows(algebra,labels):
    if algebra.get("type")!="A" or labels is None: return None
    return [sum(labels[i:]) for i in range(len(labels)) if sum(labels[i:])]
