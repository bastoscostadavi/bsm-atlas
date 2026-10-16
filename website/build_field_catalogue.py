#!/usr/bin/env python3
"""Build the deliberately small catalogue from the immutable 50-paper snapshot.

No original SQLite table or scientific-review state is modified. The output is
a traceable, scoped projection, not a fresh full-text extraction or a proof of
physical-theory equivalence. Regimes are never combined into one spectrum.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
from field_conventions import factor, gauge_factors, rational, primitive_scale, irrep_token, dynkin, dimension_a, young_rows, parse_tuple, dynkin_representation, REPRESENTATION_CONVENTION
from spacetime_conventions import CONVENTION as LORENTZ_CONVENTION, spacetime, field_reps

SITE=Path(__file__).resolve().parent
ROOT=SITE.parent
sys.path.insert(0,str(ROOT/'atlas'))
from catalogue_identity import canonicalize,normalize_spec,from_regime,IncompleteContent,conjugate as conjugate_irrep
VERSION="gauge-matter-3"
DATE="2026-10-16"
SM_FACTORS=[factor("SU(3)","colour"),factor("SU(2)","weak_L"),factor("U(1)","hypercharge")]


def multiplet(label,kind,rep,copies=1,reality=None):
    chirality="left-handed Weyl" if kind=="F" else None
    components=[{'factor':a['label'],'role':a['role'],'value':v,'dynkin':dynkin(a,v) if a['type']!='U1' else None,'youngRows':young_rows(a,dynkin(a,v)) if a['type']!='U1' else None} for a,v in zip(SM_FACTORS,rep)]
    return {"label":label,"kind":kind,"representation":rep,"dynkinRepresentation":dynkin_representation(components),"components":components,"copies":copies,"reality":reality,"chirality":chirality,"lorentz":field_reps([kind],chirality=chirality or '',reality=reality)}


SM_F=[multiplet(n,"F",r,3) for n,r in [("Q",["3","2","1"]),("uᶜ",["bar(3)","1","-4"]),("dᶜ",["bar(3)","1","2"]),("L",["1","2","-3"]),("eᶜ",["1","1","6"])]]
SM_H=[multiplet("H","S",["1","2","3"],1,"complex")]
MSSM=[]
for p in SM_F:
    MSSM.extend([p,multiplet("scalar "+p["label"],"S",p["representation"],3,"complex")])
for name,q in [("H_u","3"),("H_d","-3")]:
    MSSM.extend([multiplet(name,"S",["1","2",q],1,"complex"),multiplet("higgsino "+name,"F",["1","2",q])])
MSSM.extend([multiplet("gluino","F",["8","1","0"]),multiplet("wino","F",["1","3","0"]),multiplet("bino","F",["1","1","0"])])
TEMPLATES={"F_SM":{"name":"SM fermions","fields":SM_F},"H_SM":{"name":"SM Higgs","fields":SM_H},"R_SM":{"name":"SM matter","fields":SM_F+SM_H},"R_MSSM":{"name":"MSSM matter","fields":MSSM}}


def display_rep(values,factors):
    nonabelian=[v if v is not None else "?" for v,f in zip(values,factors) if f["type"]!="U1"]
    charges=[v if v is not None else "?" for v,f in zip(values,factors) if f["type"]=="U1"]
    return "("+", ".join(nonabelian)+("; "+", ".join(charges) if charges else "")+")"


def field_type(field):
    kind=(field.get("field_kind") or "").lower()
    chirality=(field.get("chirality") or "").lower()
    if "superfield" in kind or "supermultiplet" in kind:
        return ["F"] if "gauge vector" in kind else ["S","F"]
    if any(x in kind for x in ["higgsino","gaugino","gluino","wino","bino","weyl","majorana","dirac","two-component"]):
        return ["F_D"] if "dirac" in kind else ["F"]
    if any(x in kind for x in ["scalar","higgs","flavon","goldstone","pion"]): return ["S"]
    if "vector" in kind and not any(x in kind for x in ["vector-like","vectorlike"]): return ["V"]
    if any(x in kind for x in ["fermion","quark","lepton","neutrino","spinor","gaugino","higgsino"]):
        return ["F_D"] if any(x in kind+" "+chirality for x in ["dirac","vector-like","vectorlike","left and right"]) else ["F"]
    if any(x in kind for x in ["vector","proca"]): return ["V"]
    return ["?"]


def excluded(field):
    kind=(field.get("field_kind") or "").lower()
    note=(field.get("scope_note") or "").lower()
    return any(x in kind for x in ["component coordinate","matrix organization","mass eigenstate","angular mode","graviton","gravitational","metric","gauge connection","gauge field strength","gauge vector superfield","gauge superfield","gauge component","gauge boson","gauge-boson","massive-vector combination","spurion","operator collection","superfield operator"]) or "no independent additional degrees" in note


def copies(field):
    text=(field.get("multiplicity") or "").strip()
    m=re.match(r"^(\d+)(?:\b|;)",text)
    return int(m.group(1)) if m else None


def main_data(database,curations):
    original_hash=hashlib.sha256(database.read_bytes()).hexdigest()
    with sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True) as con:
        con.row_factory=sqlite3.Row
        def all_rows(table): return [dict(r) for r in con.execute("SELECT * FROM "+table)]
        tables={name:all_rows(name) for name in ["papers","paper_versions","paper_profiles","theory_specifications","theory_regimes","theory_fields","theory_field_representations","theory_gauge_groups","theory_gauge_factors","paper_theory_links","theory_assertion_links","paper_assertions","paper_assertion_evidence","evidence_refs"]}
    index=lambda name,key:{r[key]:r for r in tables[name]}
    field_index=index("theory_fields","field_id")
    group_index=index("theory_gauge_groups","group_id")
    factor_index=index("theory_gauge_factors","factor_id")
    assertion_index=index("paper_assertions","assertion_id")
    evidence_index=index("evidence_refs","evidence_id")
    spec_index=index("theory_specifications","model_id")
    ev_by_assertion=defaultdict(list)
    for r in tables["paper_assertion_evidence"]: ev_by_assertion[r["assertion_id"]].append(r["evidence_id"])
    supports=defaultdict(list)
    for r in tables["theory_assertion_links"]: supports[(r["target_kind"],r["target_id"],r["model_id"])].append(r)

    def source_evidence(kind,target,model):
        result=[]
        for support in supports.get((kind,target,model),[]):
            assertion=assertion_index[support["assertion_id"]]
            result.append({"supportId":support["support_id"],"assertionId":assertion["assertion_id"],"claim":assertion["claim_text"],"basis":assertion["basis"],"review":assertion["review_status"],"stance":support["support_stance"],"locations":[{k:evidence_index[e].get(k) for k in ["evidence_id","paper_version_id","locator","pdf_page","printed_page"]} for e in ev_by_assertion[assertion["assertion_id"]]]})
        return result

    def make_regime(model,regime):
        source_groups=[g for g in tables["theory_gauge_groups"] if g["regime_id"]==regime["regime_id"]]
        raw_fields=[f for f in tables["theory_fields"] if f["regime_id"]==regime["regime_id"]]
        slots=[];group_slots={};raw_factor_slots={};notes=[]
        for group in source_groups:
            if model["model_id"]=="littlest-higgs-minimal" and group["group_id"]==95:
                notes.append("The diagonal EW group is an alternative broken-phase description, not a further direct-sum factor. Its source representation rows remain unconverted in this UV view.")
                continue
            gf=gauge_factors(group["group_label"])
            if not gf: notes.append("Unresolved gauge algebra: "+str(group["group_label"]))
            group_slots[group["group_id"]]=[]
            available=[f for f in tables["theory_gauge_factors"] if f["group_id"]==group["group_id"]]
            used=set()
            for f in gf:
                slot={**f,"key":str(group["group_id"])+":"+str(len(group_slots[group["group_id"]])),"groupId":group["group_id"],"normalization":None}
                local=len(slots);slots.append(slot);group_slots[group["group_id"]].append(local)
                candidates=[]
                for original in available:
                    parsed=gauge_factors(original["factor_label"])
                    if original["factor_id"] not in used and parsed and parsed[0]["id"]==f["id"]: candidates.append((original,parsed[0]))
                unique_type=sum(x["id"]==f["id"] for x in gf)==1
                chosen=next((r for r,p in candidates if p["role"]==f["role"]),candidates[0][0] if len(candidates)==1 and unique_type else None)
                if chosen:
                    raw_factor_slots[chosen["factor_id"]]=local;used.add(chosen["factor_id"])
        baseline=curations["baselines"].get(model["model_id"])
        # An explicitly inherited SM baseline supplies colour locally when a
        # source records only its EW representation scope. No new field charge
        # is filled by this expansion.
        if baseline in {"R_SM","F_SM","R_MSSM"} and [s["id"] for s in slots]==["A1","u1"]:
            slots.append({**factor("SU(3)","colour"),"key":"baseline-colour","groupId":None,"normalization":None})
            notes.append("Colour algebra inherited from the declared baseline; source representations below may cover only the EW subgroup.")
        elif baseline in {"R_SM","F_SM","R_MSSM"} and len(slots)==1 and slots[0]["type"]=="U1" and slots[0]["role"]!="hypercharge":
            slots.extend({**a,"key":"baseline-"+a["role"],"groupId":None,"normalization":None} for a in SM_FACTORS)
            notes.append("SM algebra supplied by the declared baseline; source rows describe only the added Abelian sector. Missing new-field SM assignments are not filled.")
        # Fixed Cartan-family/rank order, independent of the source product
        # order. Role labels disambiguate repeated factors; hypercharge is the
        # first Abelian slot whenever identified.
        ordering=sorted(range(len(slots)),key=lambda i:(slots[i]["type"]=="U1",slots[i]["type"] if slots[i]["type"]!="U1" else "",-(slots[i]["rank"] or 0),0 if slots[i]["role"]=="hypercharge" else 1,slots[i]["role"],i))
        complete_factors=[slots[i] for i in ordering]
        all_components=[];fields=[]
        for f in raw_fields:
            source_reps=[r for r in tables["theory_field_representations"] if r["field_id"]==f["field_id"]]
            values=[None]*len(slots);rep_ids=[];unconverted=[]
            for rep in source_reps:
                rep_ids.append(rep["representation_id"])
                if rep["factor_id"] is not None:
                    position=raw_factor_slots.get(rep["factor_id"])
                    if position is None: unconverted.append("Unmapped source factor "+str(rep["factor_id"]));continue
                    incoming=rep["exact_charge"] if slots[position]["type"]=="U1" else (rep["representation_label"] or "").split(",")[0]
                    assignments=[(position,incoming)]
                else:
                    positions=group_slots.get(rep["group_id"],[])
                    override=curations["source_irrep_charge_overrides"].get(str(rep["representation_id"]))
                    parsed,method=parse_tuple(rep,[slots[i] for i in positions],override)
                    if not parsed: unconverted.append(rep["representation_label"] or "Unspecified representation");continue
                    assignments=list(zip(positions,parsed))
                for position,incoming in assignments:
                    value=incoming if slots[position]["type"]=="U1" else irrep_token(incoming)
                    if values[position] is not None and values[position]!=value:
                        values[position]=None;unconverted.append("Conflicting assignments for "+slots[position]["label"])
                    else: values[position]=value
            completion=curations.get("field_component_completions",{}).get(str(f["field_id"]))
            if completion and "same_as" in completion:
                completion=curations["field_component_completions"][completion["same_as"]]
            if completion:
                matches=[i for i,a in enumerate(slots) if a["role"]==completion["role"] and a["id"]==completion["algebra"]]
                if len(matches)!=1 or values[matches[0]] is not None:
                    raise ValueError("Completion would overwrite or ambiguously assign field "+str(f["field_id"]))
                values[matches[0]]=completion["value"]
            item={"sourceFieldId":f["field_id"],"label":f["field_label"],"sourceKind":f["field_kind"],"kinds":field_type(f),"copies":copies(f),"sourceMultiplicity":f["multiplicity"],"sourceChirality":f["chirality"],"reality":f["field_reality_condition"],"inherited":f["inherited_baseline_label"],"sourceNote":f["scope_note"],"excludedCoordinate":excluded(f),"values":values,"sourceRepresentationIds":rep_ids,"unconverted":unconverted,"sourceRepresentations":[{k:r.get(k) for k in ["representation_id","representation_label","exact_charge","source_notation","normalization_note"]} for r in source_reps],"curatedCompletion":completion,"evidence":source_evidence("field",f["field_id"],model["model_id"])+[e for rid in rep_ids for e in source_evidence("field_representation",rid,model["model_id"])]}
            if any(isinstance(v,str) and v.startswith("[") for v in values):
                item["copies"]=None
                item["unconverted"].append("Indexed family charge vector: not identical copies of one irrep.")
            if baseline=="R_MSSM" and model["model_id"] in {"mssm-rpc-conventional-soft","mssm-rpv-general"}: item["inherited"]="R_MSSM reference template"
            fields.append(item)
        # Exact common normalization for each Abelian factor. Baseline units are
        # reference conventions, not newly claimed source-extracted multiplets.
        for position,s in enumerate(slots):
            if s["type"]!="U1": continue
            assigned=[f for f in fields if f["values"][position] is not None and not f["excludedCoordinate"]]
            numeric=[rational(f["values"][position]) for f in assigned]
            role=s["role"]
            reference=None
            if role=="hypercharge":
                reference=Fraction(1,int(curations["hypercharge_source_multiplier_to_6Y"].get(str(s["groupId"]),"6")))
            missing=any(not f["excludedCoordinate"] and f["values"][position] is None for f in fields)
            scale=primitive_scale(numeric+([reference] if reference else [])) if all(v is not None for v in numeric) and (reference is not None or not missing) else None
            status="primitive_recorded_assignment" if scale else "symbolic_or_unresolved" if assigned else "not_recorded"
            if reference and scale: status="SM_reference_units_only" if missing else "primitive_with_SM_reference"
            if baseline and reference and scale and scale!=1/reference:
                raise ValueError("An exotic hypercharge changes the shared baseline unit; define a scaled baseline before publishing "+model["model_id"])
            if scale:
                for f,q in zip(assigned,numeric): f["values"][position]=str(int(q*scale))
            else:
                for f in assigned:
                    if rational(f["values"][position]) not in {None,Fraction(0)}:
                        f["values"][position]="source:"+str(f["values"][position])
            if s["groupId"]==38:
                chi={"-1/(2 sqrt(10))":"-1","3/(2 sqrt(10))":"3","-5/(2 sqrt(10))":"-5"}
                if assigned and all(f["values"][position] in chi for f in assigned):
                    for f in assigned: f["values"][position]=chi[f["values"][position]]
                    scale="2 sqrt(10)";status="primitive_recorded_assignment"
            s["normalization"]={"status":status,"scale":str(scale) if scale is not None else None,"scope":"recorded assignment plus declared SM reference unit" if reference else "recorded assignment only; spectrum may be incomplete","sourceReferenceUnit":str(reference) if reference else None,"sign":"positive scaling; source generator orientation retained","couplingRule":"g_atlas = g_source / scale" if scale else None}
        rendered=[]
        for f in fields:
            values=[f["values"][i] for i in ordering]
            f.pop("values")
            # Keep handedness explicit. A right-handed 4D Weyl representation
            # is conjugated as a whole, never by changing just the U(1) sign.
            right=(f["sourceChirality"] or "").lower().startswith("right")
            field_scope=spacetime(regime,{"field_kind":f["sourceKind"]})
            four_dimensional=field_scope["dimension"]=='4'
            if right and four_dimensional and f["kinds"]==["F"]:
                changed=[]
                for v,a in zip(values,complete_factors):
                    if v is None: changed.append(None)
                    elif a["type"]=="U1": changed.append(str(-rational(v)) if rational(v) is not None else "-("+v+")")
                    elif a["type"]=="A" and a["rank"]>1:
                        w=dynkin(a,v)
                        changed.append(v if v in {'1','Adj'} or w is not None and w==w[::-1] else v[4:-1] if v.startswith('bar(') else 'bar('+v+')')
                    else: changed.append(v)
                values=changed;f["label"]+="ᶜ";f["conversion"]="Right-handed source field rewritten as its left-handed charge conjugate."
            elif f["kinds"]==["F_D"]: f["conversion"]="One Dirac/vector-like multiplet in the displayed source representation. In four dimensions it corresponds to two left-handed Weyl multiplets in R and its conjugate; copies count Dirac multiplets, not Weyl fields. No dimensional reduction is inferred for bulk fields."
            elif f["kinds"]==["S","F"]: f["conversion"]="One chiral supermultiplet expanded as one complex scalar and one left-handed Weyl fermion; no auxiliary fields counted."
            else: f["conversion"]="Source handedness/reality retained; unspecified is not silently filled."
            f["lorentz"]=field_reps(f["kinds"],f["sourceKind"] or '',f["sourceChirality"] or '',f["reality"],field_scope,converted_right=right and four_dimensional and f["kinds"]==['F'])
            components=[];total_dimension=1
            for value,a in zip(values,complete_factors):
                weight=dynkin(a,value) if value is not None and a["type"]!="U1" else None
                dim=1 if a["type"]=="U1" else dimension_a(weight) if a["type"]=="A" else None
                if dim is None: total_dimension=None
                elif total_dimension is not None: total_dimension*=dim
                components.append({"factorKey":a["key"],"factor":a["label"],"role":a["role"],"value":value,"dynkin":weight,"youngRows":young_rows(a,weight),"dimension":dim})
            for lorentz in f['lorentz']:
                actual=deepcopy(components)
                for c,a in zip(actual,complete_factors):
                    if lorentz.get('conjugateGauge') and c['value'] is not None:
                        if a['type']=='U1':c['value']=str(-rational(c['value'])) if rational(c['value']) is not None else '−('+c['value']+')'
                        elif c['dynkin'] is not None:
                            w=conjugate_irrep({'dynkin':c['dynkin']},{'family':a['type'],'rank':a['rank']})['dynkin']
                            if w!=c['dynkin']:c['value']=c['value'][4:-1] if c['value'].startswith('bar(') else 'bar('+c['value']+')'
                            c['dynkin']=w;c['youngRows']=young_rows(a,w)
                        elif c['value'] not in {'1','Adj'}:c['value']='conj('+c['value']+')'
                    c['assignmentStatus']='source_handedness_unresolved' if lorentz['status']=='source_chirality_unresolved' else 'assigned_under_stated_conventions' if c['value'] is not None and (a['type']=='U1' and rational(c['value']) is not None or a['type']!='U1' and c['dynkin'] is not None) else 'unresolved'
                lorentz['gaugeComponents']=actual
                lorentz['dynkinRepresentation']=dynkin_representation(actual)
            f.update(components=components,representation=display_rep(values,complete_factors),dynkinRepresentation=dynkin_representation(components),dimension=total_dimension,notationComplete=bool(complete_factors) and all(v is not None and (a["type"]=="U1" and rational(v) is not None or a["type"]!="U1" and dynkin(a,v) is not None) for v,a in zip(values,complete_factors)))
            rendered.append(f)
        if not source_groups and raw_fields: notes.append("Gauge algebra not independently recorded in this regime; no cross-regime assignment invented.")
        factors_label=" ⊕ ".join(f["label"]+("_"+f["role"] if len({p["id"] for p in complete_factors})<len(complete_factors) else "") for f in complete_factors) or "not specified"
        sm_positions=[i for i,a in enumerate(complete_factors) if a["role"] in {"colour","weak_L","hypercharge"}]
        shorthand="g_SM" if [complete_factors[i]["id"] for i in sm_positions]==["A2","A1","u1"] and len(sm_positions)==len(complete_factors) else factors_label
        return {"id":regime["regime_id"],"description":regime["description_kind"],"dimension":regime["spacetime_dimension"],"algebra":shorthand,"algebraExpanded":factors_label,"algebraSignature":"+".join(sorted(f["id"] for f in complete_factors)) or "unresolved","factors":complete_factors,"baseline":baseline,"fields":rendered,"notes":notes,"sourceGroups":[{"groupId":g["group_id"],"sourceLabel":g["group_label"],"globalForm":"not part of this catalogue"} for g in source_groups]}

    model_records={}
    for model in tables["theory_specifications"]:
        model_records[model["model_id"]]={"model":model,"regimes":[make_regime(model,r) for r in tables["theory_regimes"] if r["model_id"]==model["model_id"] and r["model_revision"]==model["revision"]]}
    entries=[];seen=set()
    definitions=curations["groups"]+[{"id":m["model_id"],"name":m["display_name"],"models":[m["model_id"]],"basis":"Source-scoped structural record; no inferred equivalence with other entries."} for m in tables["theory_specifications"] if not any(m["model_id"] in g["models"] for g in curations["groups"])]
    versions=index("paper_versions","paper_version_id");profiles=index("paper_profiles","paper_version_id")
    papers=[]
    for p in tables["papers"]:
        v=next(v for v in tables["paper_versions"] if v["paper_id"]==p["paper_id"]);profile=profiles.get(v["paper_version_id"],{})
        papers.append({"id":p["paper_id"],"arxiv":v["paper_version_id"],"kind":p["source_kind"],"title":profile.get("verified_title") or v["seed_title"],"authors":profile.get("verified_authors") or v["seed_authors"],"inspectionStatus":profile.get("extraction_status"),"reviewStatus":profile.get("review_status"),"inspectedScope":profile.get("inspected_scope"),"limitations":profile.get("extraction_limitations"),"noModelReason":profile.get("no_model_link_reason")})
    for definition in definitions:
        records=[model_records[mid] for mid in definition["models"]]
        source_links=[l for l in tables["paper_theory_links"] if l["model_id"] in definition["models"]]
        paper_ids=sorted({versions[l["paper_version_id"]]["paper_id"] for l in source_links})
        variants=[]
        for record in records:
            m=record["model"];seen.add(m["model_id"])
            variants.append({"id":m["model_id"],"name":m["display_name"],"revision":m["revision"],"scope":m["scope_note"],"baselineSource":m["baseline_label"],"baselineParent":curations["inherits"].get(m["model_id"]),"regimes":record["regimes"]})
        primary=next((r for v in variants for r in v["regimes"] if r["factors"] and r["fields"]),next((r for v in variants for r in v["regimes"] if r["factors"]),variants[0]["regimes"][0] if variants[0]["regimes"] else None))
        if primary is None: raise ValueError("No description regime for "+definition["id"])
        # Explicit parent references supply navigation only; they never copy a
        # parent's spectrum into a different regime without a source decision.
        additions=[f for f in primary["fields"] if not f["inherited"] and not f["excludedCoordinate"]]
        if primary["baseline"]=="R_MSSM" and definition["id"]=="mssm-matter": additions=[]
        state="recorded_content" if primary["factors"] and (additions or primary["baseline"]) and all(f["notationComplete"] and f["copies"] is not None and f["kinds"]!=["?"] for f in additions) else "partial"
        if not additions and definition["id"]!="mssm-matter": state="partial"
        if any(v["baselineParent"] for v in variants) and not primary["baseline"]: state="partial"
        if any(p["id"] in paper_ids and p["inspectionStatus"]=="partial" for p in papers): state="partial"
        if any(f["type"] in {"parameterized","unknown","unresolved_sp_convention"} for f in primary["factors"]): state="parameterized"
        if definition["id"]=="sm-eft-matter": state="reference"
        entries.append({"id":definition["id"],"name":curations.get("display_names",{}).get(definition["id"],definition["name"]),"paperIds":paper_ids,"algebra":primary["algebra"],"algebraExpanded":primary["algebraExpanded"],"algebraSignature":primary["algebraSignature"],"baseline":primary["baseline"],"primaryRegime":primary["id"],"primaryVariant":next(v["id"] for v in variants if primary in v["regimes"]),"status":state,"groupingBasis":definition["basis"],"variants":variants,"summaryFields":[{"label":f["label"],"kinds":f["kinds"],"copies":f["copies"],"representation":f["representation"],"dynkinRepresentation":f["dynkinRepresentation"],"reality":f["reality"]} for f in additions],"catalogueEligible":not all(mid in curations["excluded_models"] for mid in definition["models"])})
    if seen!=set(spec_index): raise ValueError("Source model coverage mismatch")
    references=[e for e in entries if not e["catalogueEligible"]]
    entries=[e for e in entries if e["catalogueEligible"]]
    for e in entries:
        try:
            if e['status']!='recorded_content':raise IncompleteContent('Incomplete/parameterized inventory: resolve the source scope before a uniqueness claim')
            r=next(r for v in e['variants'] for r in v['regimes'] if r['id']==e['primaryRegime'])
            if not r['baseline'] and e['id'] not in curations['full_inventory_without_baseline']:raise IncompleteContent('A recorded sector is not an attested full SM-containing inventory')
            spec=normalize_spec(from_regime(r,TEMPLATES,dynkin))
            identity=canonicalize(spec)
            e['identity']={'status':'complete_under_stated_conventions','fingerprint':identity['fingerprint'],'input':spec,'canonical':json.loads(identity['canonical_json'])}
        except IncompleteContent as error:
            e['identity']={'status':'unresolved','reason':str(error),'fingerprint':None}
    for p in papers:
        p["entryIds"]=[e["id"] for e in entries if p["id"] in e["paperIds"]]
        p["referenceNotes"]=[curations["excluded_models"][v["id"]] for e in references if p["id"] in e["paperIds"] for v in e["variants"] if v["id"] in curations["excluded_models"]]
    if len(papers)!=50: raise ValueError("The release must account for all 50 seed sources")
    seed_paper_count=len(papers)
    for p in curations.get("reference_papers",[]):
        if any(p["id"]==s["id"] or p["arxiv"].split("v")[0]==s["arxiv"].split("v")[0] for s in papers):
            raise ValueError("Duplicate reference paper: "+p["id"])
        papers.append({**p,"entryIds":[],"referenceNotes":[],"referenceOnly":True})
    source_ids={f["sourceFieldId"] for e in entries+references for v in e["variants"] for r in v["regimes"] for f in r["fields"]}
    if source_ids!=set(field_index): raise ValueError("A source field was omitted")
    if hashlib.sha256(database.read_bytes()).hexdigest()!=original_hash: raise ValueError("Source changed during read-only build")
    return {"version":VERSION,"publishedOn":DATE,"sourceDatabaseSha256":original_hash,"representationConvention":REPRESENTATION_CONVENTION,"lorentzConvention":LORENTZ_CONVENTION,"sourceReview":"All underlying assertions remain unchecked and model links provisional. This catalogue is a notation projection of the scoped extraction, not a new full-text review.","scope":"BSM gauge/matter content and linked source papers only. Pure convention/theory/tool references, uninstantiated frameworks and operator-only SM inventories do not become BSM model rows.","templates":TEMPLATES,"references":[{"title":"Dynkin labels and representation conventions (not a model row)","url":"https://arxiv.org/abs/1206.6379"}],"counts":{"papers":len(papers),"seedPapers":seed_paper_count,"sourceModels":len(spec_index),"entries":len(entries),"sourceFields":len(source_ids),"referenceRecords":len(references)},"entries":sorted(entries,key=lambda e:(min(e["paperIds"] or ["Z"]),e["name"])),"referenceRecords":references,"papers":sorted(papers,key=lambda p:p["id"])}


def write_outputs(data,check=False):
    payload=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    flat=io.StringIO();writer=csv.writer(flat,lineterminator='\n')
    writer.writerow(["entry_id","name","gauge_algebra","baseline","additional_recorded_multiplets","coverage","papers","source_model_ids"])
    for e in data["entries"]:
        writer.writerow([e["id"],e["name"],e["algebraExpanded"],e["baseline"] or "", " | ".join("/".join(f["kinds"])+" "+str(f["copies"] if f["copies"] is not None else "?")+" × "+f["dynkinRepresentation"]+" "+f["label"] for f in e["summaryFields"]),e["status"],";".join(e["paperIds"]),";".join(v["id"] for v in e["variants"])])
    files={SITE/"field-catalogue.json":payload+"\n",SITE/"entry.schema.json":(ROOT/"atlas"/"entry.schema.json").read_text(encoding="utf-8"),ROOT/"atlas"/"FIELD_CONTENT_CATALOGUE.json":payload+"\n",SITE/"field-catalogue-data.js":"window.FIELD_CATALOGUE = "+payload+";\n",SITE/"downloads"/"field-catalogue.csv":flat.getvalue()}
    for path,content in files.items():
        if check:
            if not path.exists() or path.read_bytes()!=content.encode("utf-8"): raise ValueError("Stale generated catalogue: "+str(path))
        else:
            path.parent.mkdir(exist_ok=True);path.write_bytes(content.encode("utf-8"))
    if not check:
        database=SITE/"downloads"/"field-catalogue.sqlite"
        with sqlite3.connect(database) as con:
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript("""
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS entries(entry_id TEXT PRIMARY KEY,name TEXT NOT NULL,gauge_algebra TEXT NOT NULL,baseline TEXT,coverage TEXT NOT NULL,source_variants_json TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS papers(paper_id TEXT PRIMARY KEY,arxiv_version TEXT NOT NULL,title TEXT NOT NULL,inspection_status TEXT,review_status TEXT);
              CREATE TABLE IF NOT EXISTS entry_papers(entry_id TEXT REFERENCES entries(entry_id),paper_id TEXT REFERENCES papers(paper_id),PRIMARY KEY(entry_id,paper_id));
              CREATE TABLE IF NOT EXISTS regimes(regime_id INTEGER PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(entry_id),source_model_id TEXT NOT NULL,description TEXT,spacetime_dimension TEXT,gauge_algebra TEXT NOT NULL,baseline TEXT,factors_json TEXT NOT NULL,notes_json TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS multiplets(multiplet_id TEXT PRIMARY KEY,entry_id TEXT NOT NULL REFERENCES entries(entry_id),source_model_id TEXT NOT NULL,regime_id INTEGER NOT NULL,field_label TEXT NOT NULL,field_types TEXT NOT NULL,representation TEXT NOT NULL,copies INTEGER,representation_dimension INTEGER,source_field_id INTEGER NOT NULL,source_rows_json TEXT NOT NULL,components_json TEXT NOT NULL,evidence_json TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS spacetime_representations(representation_id TEXT PRIMARY KEY,multiplet_id TEXT NOT NULL REFERENCES multiplets(multiplet_id),component_kind TEXT NOT NULL,spacetime_dimension TEXT,lorentz_algebra TEXT NOT NULL,representation_label TEXT NOT NULL,status TEXT NOT NULL,representation_json TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS component_gauge_representations(component_id TEXT NOT NULL REFERENCES spacetime_representations(representation_id),factor_key TEXT NOT NULL,algebra_id TEXT NOT NULL,role TEXT,dynkin_json TEXT,charge TEXT,representation_label TEXT,status TEXT NOT NULL,PRIMARY KEY(component_id,factor_key));
              CREATE TABLE IF NOT EXISTS content_signatures(fingerprint TEXT PRIMARY KEY,schema_version TEXT NOT NULL,canonical_json TEXT NOT NULL,canonical_entry_id TEXT NOT NULL REFERENCES entries(entry_id));
              CREATE TABLE IF NOT EXISTS entry_identity(entry_id TEXT PRIMARY KEY REFERENCES entries(entry_id),status TEXT NOT NULL,reason TEXT,fingerprint TEXT REFERENCES content_signatures(fingerprint),algebra_signature TEXT NOT NULL,input_json TEXT);
            """)
            for name in ["entry_identity","content_signatures","entry_papers","component_gauge_representations","spacetime_representations","multiplets","regimes","entries","papers","metadata"]: con.execute("DELETE FROM "+name)
            con.executemany("INSERT INTO metadata VALUES (?,?)",[("convention_version",VERSION),("source_sha256",data["sourceDatabaseSha256"]),("scope",data["scope"]),("templates_json",json.dumps(data["templates"],ensure_ascii=False))])
            con.execute("INSERT INTO metadata VALUES (?,?)",('lorentz_convention_json',json.dumps(LORENTZ_CONVENTION,ensure_ascii=False)))
            con.execute("INSERT INTO metadata VALUES (?,?)",('representation_convention_json',json.dumps(REPRESENTATION_CONVENTION,ensure_ascii=False)))
            for p in data["papers"]: con.execute("INSERT INTO papers VALUES (?,?,?,?,?)",(p["id"],p["arxiv"],p["title"],p["inspectionStatus"],p["reviewStatus"]))
            for e in data["entries"]:
                con.execute("INSERT INTO entries VALUES (?,?,?,?,?,?)",(e["id"],e["name"],e["algebraExpanded"],e["baseline"],e["status"],json.dumps([{k:v[k] for k in ["id","revision","scope","baselineSource","baselineParent"]} for v in e["variants"]],ensure_ascii=False)))
                con.executemany("INSERT INTO entry_papers VALUES (?,?)",[(e["id"],p) for p in e["paperIds"]])
                for v in e["variants"]:
                    for r in v["regimes"]:
                        con.execute("INSERT INTO regimes VALUES (?,?,?,?,?,?,?,?,?)",(r["id"],e["id"],v["id"],r["description"],r["dimension"],r["algebraExpanded"],r["baseline"],json.dumps(r["factors"],ensure_ascii=False),json.dumps(r["notes"],ensure_ascii=False)))
                        for f in r["fields"]:
                            con.execute("INSERT INTO multiplets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(e["id"]+":"+str(f["sourceFieldId"]),e["id"],v["id"],r["id"],f["label"],"/".join(f["kinds"]),f["representation"],f["copies"],f["dimension"],f["sourceFieldId"],json.dumps(f,ensure_ascii=False),json.dumps(f["components"],ensure_ascii=False),json.dumps(f["evidence"],ensure_ascii=False)))
                            for i,l in enumerate(f['lorentz']):
                                key=e['id']+':'+str(f['sourceFieldId'])
                                con.execute('INSERT INTO spacetime_representations VALUES (?,?,?,?,?,?,?,?)',(key+':'+str(i),key,l['component'],l['spacetime']['dimension'],l['spacetime']['algebra'],l['label'],l['status'],json.dumps(l,ensure_ascii=False)))
                                for a,c in zip(r['factors'],l['gaugeComponents']):
                                    con.execute('INSERT INTO component_gauge_representations VALUES (?,?,?,?,?,?,?,?)',(key+':'+str(i),a['key'],a['id'],a['role'],json.dumps(c['dynkin']) if c['dynkin'] is not None else None,c['value'] if a['type']=='U1' else None,c['value'],c['assignmentStatus']))
            con.commit()
            for e in data['entries']:
                identity=e['identity'];h=identity['fingerprint']
                if h:con.execute('INSERT OR IGNORE INTO content_signatures VALUES (?,?,?,?)',(h,'field-content-1',json.dumps(identity['canonical'],sort_keys=True,separators=(',',':')),e['id']))
                r=next(r for v in e['variants'] for r in v['regimes'] if r['id']==e['primaryRegime'])
                signature=sorted([{'family':a['type'],'rank':a['rank']} for a in r['factors']],key=lambda a:(a['family']=='U1',a['family'],-(a['rank'] or 0)))
                con.execute('INSERT INTO entry_identity VALUES (?,?,?,?,?,?)',(e['id'],identity['status'],identity.get('reason'),h,json.dumps(signature,sort_keys=True,separators=(',',':')),json.dumps(identity['input'],ensure_ascii=False) if h else None))
            con.commit()
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or con.execute("PRAGMA foreign_key_check").fetchall(): raise ValueError("Invalid catalogue SQLite")
    print("Catalogue: "+str(data["counts"])+("; generated files current" if check else "; source database unchanged"))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    curations=json.loads((ROOT/"atlas"/"field_content_curations.json").read_text(encoding="utf-8"))
    write_outputs(main_data(ROOT/"atlas"/"atlas.sqlite",curations),check=args.check)
