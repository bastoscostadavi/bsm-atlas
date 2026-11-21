"""Single-pass Luna extraction of models and literature connections.

The existing mirror alone downloads TeX. This runner reads verified local sources,
uses tool-free workers and serializes canonical intake. It never retries a paid
attempt automatically or deletes retained source members. Run --help for commands.
"""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from threading import Event
import unicodedata

from .catalogue import ROOT, SOURCE, load, source_lock, exclusive_lock, write_json, validate, identity
from .harvest import context, prompt, extracted_entries, reconcile_entry, worker_command, check_worker, check_prompt_size, event_usage
from .papers import job_id
from .citations import base_id
from .corpus import CORPUS
from .corpus_queue import read_source, AwaitingSource, enqueue
from .literature import load_links, path_for
from .extraction_quality import assessment as quality_assessment

MODEL = 'gpt-6-luna'
DEFAULT_EXECUTABLE = '/Users/davicosta/.nvm/versions/node/v22.17.1/bin/codex'
TERMINAL = {'ingested', 'invalid', 'retry', 'already_recorded', 'interrupted', 'source_unavailable'}
# Exact immutable specification keys; references and uniqueness are always checked.
_INTAKE_SPECIFICATION_CACHE = {}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def digest(raw):
    return sha256(raw).hexdigest()


def obj(properties):
    return {'type': 'object', 'additionalProperties': False,
            'required': list(properties), 'properties': properties}


def response_schema():
    string = {'type': 'string'}
    array = lambda item: {'type': 'array', 'items': item}
    evidence = array(obj({'quote': string, 'locator': string}))
    def assessment(key, positive):
        kind='problems' if key=='problem_id' else 'mechanisms'
        return obj({key: {'type':'string','enum':[v['id'] for v in taxonomies()[kind][kind]]}, 'status': {'type': 'string', 'enum': [positive, 'mentions_only', 'unclear']},
                    'rationale': string, 'evidence': evidence})
    entry = obj({'id': {'type':'string','pattern':'^[a-z0-9]+(?:-[a-z0-9]+)*$'}, 'name': string, 'specification_json': {'type':'string',
                 'description':'JSON string: for explicitly inherited SM/MSSM with unchanged algebra use {"reference_spectrum":"R_SM" or "R_MSSM","additions":[new matter rows]}; otherwise a complete conventional field-content specification.'},
                 'locators': array(string), 'problems': array(assessment('problem_id', 'addresses')),
                 'mechanisms': array(assessment('mechanism_id', 'implements'))})
    return obj({'outcome': {'type': 'string', 'enum': ['entries', 'skip', 'retry']},
                'reason': string, 'coverage': {'type': 'string', 'enum': ['full_text', 'partial_text', 'unusable']},
                'confidence': {'type':'string','enum':['high','medium','low']},
                'uncertainty_reason': string,
                'entries': array(entry)})


def schema_check(value, schema):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError('Unexpected/missing JSON object keys')
        for key in value:
            schema_check(value[key], schema['properties'][key])
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError('Expected array')
        for item in value:
            schema_check(item, schema['items'])
    elif kind == 'string':
        if not isinstance(value, str) or ('enum' in schema and value not in schema['enum']):
            raise ValueError('Expected string/allowed status')
    else:
        raise ValueError('Unsupported response schema')


def taxonomies():
    problems = read(ROOT / 'experiments/problem-mapping-luna/problems.json')
    problems = {**problems, 'categories': [c for c in problems['categories'] if c['id'] != 'established_theory_dynamics'],
                'problems': [p for p in problems['problems'] if p['category_id'] != 'established_theory_dynamics']}
    return {'problems': problems, 'mechanisms': read(ROOT / 'experiments/mechanism-mapping-luna/mechanisms.json')}


JOINT_INSTRUCTIONS = '''
JOINT MODEL AND CONNECTION EXTRACTION
Return a single JSON object using the JOINT OUTPUT CONTRACT, which supersedes
only the basic output shape in ATLAS INSTRUCTIONS. Scientific scope and all
representation conventions remain unchanged. Read the entire usable paper once.
Extract every complete eligible model specified or explicitly adopted in the
paper, even if it is familiar or was introduced in another paper. Do not extract
bare motivations, SM-only operator EFTs, nonlinear effective inventories, or
invent missing ultraviolet fields. New scalar/fermion extensions of the SM ARE
eligible when their complete source-supported renormalizable inventory is given.
Do not include gauge bosons as matter. Normalize right-handed fermions by charge
conjugation; use exact Dynkin labels and the scalar/multiplicity conventions.

REFERENCE-SPECTRUM RECIPES (required for explicitly inherited SM/MSSM)
When this paper explicitly adopts the SM or MSSM with the SAME gauge algebra,
do not transcribe all inherited multiplets again. Set specification_json to the
JSON string encoding {"reference_spectrum":"R_MSSM","additions":[]} for the
MSSM, or {"reference_spectrum":"R_SM","additions":[...new matter rows...]} for
an SM extension. Code copies the reference inventory EXACTLY and adds the stated
rows. Additions use the reference factor keys colour, weak_L, hypercharge and
integer hypercharges in the SAME normalization as the supplied reference.
Each added row has lorentz, reality, copies, gauge_representations as usual.
The recipe has exactly those two keys; it cannot remove or alter inherited rows.
Do not put the baseline into additions or count inherited fields a second time.
R_SM with no additions is the excluded unextended SM. Use R_MSSM with no additions
for full-MSSM parameter benchmarks such as CMSSM, not a new transcription.
Use a recipe only where this paper explicitly establishes the inheritance, with
source locators. A model name in a bibliography is insufficient. If the algebra
changes or inherited charges are modified, supply the complete conventional
specification instead. Missing information is never supplied by assuming a recipe.

For EACH extracted model, assess the supplied fixed problem and mechanism
vocabularies. Use only this paper's text. A familiar name or the presence of a
particle alone is not evidence. The unit is (paper, exact model, problem/mechanism).
Do not transfer applications between variants, sectors, benchmarks or scales
without explicit source support. Do not invent taxonomy IDs. Categories are not
individual problems/mechanisms. Multiple positive links may apply to one entry;
no positive link is also a valid result. Do not add a model solely to attach a link.

problems status=addresses: the paper explicitly proposes, develops, analyzes,
tests or constrains THIS model as a mechanism/candidate for the defined problem.
This is the existing website's literature-association meaning: it does not assert
that a viable solution was demonstrated; a negative result can still count.
mechanisms status=implements: the paper actually specifies or analyzes THIS model
as a realization of the defined mechanism. A name, motivation or background
citation alone does not establish implementation.
mentions_only: a source mention without an established model-specific relation.
unclear: plausible but ambiguous attribution or inadequate text. Neither creates
a positive link. Output sparse arrays: omit pairs without any relevant mention.
For partial text, absent links remain unknown, not evidence that the model cannot
address a problem or implement a mechanism. Mark coverage honestly; an abstract
alone is unusable and must not yield a model.

Every positive or mentions_only assessment needs a nonempty rationale and at
least one SHORT EXACT CONTIGUOUS source quotation of at most 35 words. Supply
L000001-style line labels from the numbered paper, plus section/equation/table
when useful. Quotes omit added line-label prefixes. Do not paraphrase, splice,
invent page numbers or quote the bibliography. A generic problem statement plus
an unrelated field table is not sufficient to attribute an application. Use
several separate short quotations when needed to bridge attribution.

JOINT OUTPUT CONTRACT
outcome: entries / skip / retry; nonempty reason; coverage: full_text /
partial_text / unusable. entries is empty for skip or retry. Each entry contains
id, name, specification_json (exact specification as a JSON STRING), nonempty
locators, problems and mechanisms. problems items have problem_id, status,
rationale, evidence[{quote,locator}]. mechanisms items have mechanism_id, status,
rationale, evidence[{quote,locator}]. Include all these keys; use empty arrays
where appropriate. Keep id unique within this response. The coordinator merges
canonical matches and remaps their connections to the accepted catalogue ID;
no second-model review is performed. Do not put connections inside specification.

CONFIDENCE AND UNCERTAINTY (extraction metadata, never part of specification)
For every outcome, including skip and retry, return confidence high / medium /
low and uncertainty_reason. This is an ordinal self-assessment, not a numerical
probability of correctness. Evaluate completeness of model identification,
representations, charges, multiplicities and model-specific source attribution.
High means all requested decisions are directly supported and no unresolved
ambiguity was identified; it does NOT certify physical consistency or truth.
Medium means a specific interpretation or attribution remains uncertain. Low
means substantial missing context or ambiguity prevents a reliable decision.
For medium/low give a short concrete reason identifying the doubtful assignment
or missing passage. For high, uncertainty_reason can be empty. Be equally careful
when deciding that a paper has no eligible models: a confident skip must reflect
the whole usable paper, not only its abstract or a model's unfamiliar name.
Do not invent confidence for unavailable text. Use retry with low confidence.
A separate selective Terra audit may re-extract flagged papers and a random
sample of high-confidence results and skips; do not imitate an auditor or use tools.
'''


def assemble(paper, body, instructions, definitions):
    numbered = '\n'.join(f'L{i:06d}: {line}' for i, line in enumerate(body.splitlines(), 1))
    rules = instructions + '\n\n' + JOINT_INSTRUCTIONS + '\n\nFIXED TAXONOMIES:\n' + json.dumps(definitions, ensure_ascii=False)
    message = prompt(paper, numbered, rules)
    # Override the basic preamble's entry-key list explicitly at the end too.
    message += '\nReturn the JOINT OUTPUT CONTRACT above, including coverage, problems and mechanisms.\n'
    check_prompt_size(message)
    return message


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def evidence_flags(evidence, body):
    lines = body.splitlines()
    flags = set()
    for item in evidence:
        quote, locator = item['quote'], item['locator']
        if not quote.strip() or not locator.strip():
            raise ValueError('Empty evidence quote or locator')
        if normalized(quote) not in normalized(body):
            flags.add('quote_found')
        if len(quote.split()) > 35:
            flags.add('quote_within_35_words')
        labels = [int(v) for v in re.findall(r'L(\d{6})', locator)]
        if not labels or any(not 1 <= v <= len(lines) for v in labels):
            flags.add('locator_has_valid_line')
        elif not any(normalized(quote) in normalized('\n'.join(lines[max(0,v-2):min(len(lines),v+12)])) for v in labels):
            flags.add('quote_near_locator')
    return sorted(flags)


def validate_response(paper, result, body, definitions):
    schema_check(result, response_schema())
    if result['confidence'] in ('medium','low') and not result['uncertainty_reason'].strip():
        raise ValueError('Medium/low confidence requires a concrete uncertainty reason')
    plain = {'outcome': result['outcome'], 'reason': result['reason'], 'entries': [
        {k: e[k] for k in ('id', 'name', 'specification_json', 'locators')} for e in result['entries']]}
    for entry in plain['entries']:
        specification=json.loads(entry['specification_json'])
        if isinstance(specification,dict) and 'reference_spectrum' in specification:
            if set(specification)!={'reference_spectrum','additions'} or specification['reference_spectrum'] not in ('R_SM','R_MSSM') or not isinstance(specification['additions'],list):
                raise ValueError('Invalid reference-spectrum recipe')
            reference=deepcopy(read(ROOT/'atlas/reference_spectra.json')[specification['reference_spectrum']]['specification'])
            reference['matter'].extend(specification['additions'])
            entry['specification_json']=json.dumps(reference)
    entries = extracted_entries(paper, plain)
    if result['coverage'] == 'unusable' and entries:
        raise ValueError('Unusable text cannot establish model inventories')
    ids = [entry['id'] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError('Repeated local model ID')
    annotations = []
    for extracted in result['entries']:
        row = {'local_id': extracted['id'], 'problems': [], 'mechanisms': []}
        for kind, key, positive in [('problems','problem_id','addresses'),('mechanisms','mechanism_id','implements')]:
            allowed = {t['id'] for t in definitions[kind][kind]}
            seen = set()
            for link in extracted[kind]:
                term = link[key]
                if term not in allowed or term in seen:
                    raise ValueError('Unknown or repeated taxonomy ID: ' + term)
                seen.add(term)
                if not link['rationale'].strip():
                    raise ValueError('Connection lacks rationale')
                if link['status'] in (positive, 'mentions_only') and not link['evidence']:
                    raise ValueError('Positive/mentioned connection lacks source evidence')
                flags = evidence_flags(link['evidence'], body)
                if result['coverage'] != 'full_text':
                    flags.append('limited_text_coverage')
                # The public layer contains only positive associations; uncertainty
                # counts remain in the receipt, without promoting them to a link.
                if link['status'] == positive:
                    row[kind].append({'term_id': term, 'rationale': link['rationale'],
                                      'evidence': link['evidence'], 'reviewReasons': sorted(set(flags))})
        annotations.append(row)
    return entries, annotations


def compact(job):
    """Remove disposable model-call payloads, never the referenced corpus paths."""
    for name in ('prompt.txt', 'paper.txt', 'result.json', 'events.jsonl', 'stderr.txt'):
        path = Path(job) / name
        if path.is_symlink():
            raise ValueError('Refusing symlink cleanup')
        path.unlink(missing_ok=True)


def run_worker(job, paper, body, provenance, instructions, definitions, config):
    job.mkdir(parents=True, exist_ok=True)
    write_json(job/'source.json', provenance)
    write_json(job/'state.json', {'state':'running', 'started':now(), 'paper':paper})
    model=config.get('model',MODEL)
    metrics = {'provider':'openai','model':model,'reasoning':config['reasoning'], 'usage':None}
    started = time.monotonic()
    process = None
    try:
        message = assemble(paper, body, instructions, definitions)
        (job/'prompt.txt').write_text(message)
        command = worker_command(config['executable'], job, job.parent.parent/'response.schema.json', model, config['reasoning'])
        command[-1:-1] = ['-c','model_context_window=500000','-c','model_auto_compact_token_limit=475000']
        with (job/'events.jsonl').open('w') as stdout, (job/'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(command, cwd=job, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       text=True, encoding='utf-8', start_new_session=True)
            try:
                process.communicate(message, timeout=config['timeout'])
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL);process.wait()
                raise
        metrics['usage'] = event_usage(job/'events.jsonl')
        if process.returncode:
            diagnostic = (job/'stderr.txt').read_text(errors='replace')[-1500:]
            for line in (job/'events.jsonl').read_text(errors='replace').splitlines():
                try:
                    ev=json.loads(line)
                    if ev.get('type') in ('error','turn.failed'):
                        diagnostic = str(ev.get('message',ev.get('error',ev)))[:1500]
                except ValueError:
                    pass
            raise RuntimeError('Worker exited '+str(process.returncode)+': '+diagnostic)
        result=read(job/'result.json')
        try:
            entries, annotations=validate_response(paper,result,body,definitions)
        except (ValueError,TypeError,KeyError,IndexError,AttributeError) as error:
            row={'state':'invalid','reason':str(error),'paper':paper,'infrastructure':False}
            row['quality']=quality_assessment(row,result)
            return row
        row={'state':'retry' if result['outcome']=='retry' else 'ready','paper':paper,'entries':entries,'annotations':annotations,
                'coverage':result['coverage'],'outcome':result['outcome'],'reason':result['reason'],
                'confidence':result['confidence'],'uncertainty_reason':result['uncertainty_reason'],
                'result_sha256':digest((job/'result.json').read_bytes()),'infrastructure':False}
        row['quality']=quality_assessment(row,result)
        return row
    except subprocess.TimeoutExpired as error:
        row={'state':'retry','category':'worker_timeout','reason':str(error),'paper':paper,'infrastructure':False}
        row['quality']=quality_assessment(row)
        return row
    except Exception as error:
        row={'state':'retry','reason':str(error),'paper':paper,'infrastructure':process is not None}
        row['quality']=quality_assessment(row)
        return row
    finally:
        events=job/'events.jsonl'
        if events.exists():metrics['usage']=event_usage(events)
        metrics['elapsed_seconds']=round(time.monotonic()-started,3)
        metrics['finished']=now()
        write_json(job/'metrics.json',metrics)


def intake(batch, rows, source=SOURCE):
    """Idempotent code-only intake. Journal/receipts allow recovery without calls."""
    source=Path(source)
    with source_lock(source, wait=True):
        data=validate(read(source), _specification_cache=_INTAKE_SPECIFICATION_CACHE)
        links=load_links(path_for(source))
        fingerprints={identity(e['specification'])['fingerprint']:e for e in data['entries']}
        for row in rows:
            paper=deepcopy(row['paper']);job=Path(batch)/'jobs'/job_id(paper['arxiv'])
            row.setdefault('quality',quality_assessment(row))
            # Journal the validated delta before either authoritative file changes.
            write_json(job/'intake.json',row)
            existing=next((p for p in data['papers'] if p['arxiv']==paper['arxiv']),None)
            success=row['state']=='ready' and row.get('outcome') in ('entries','skip')
            if existing is None:
                paper['extraction_status']='complete' if success else 'unresolved'
                data['papers'].append(paper)
            else:
                paper=existing
                if success or paper.get('extraction_status')!='complete':
                    paper['extraction_status']='complete' if success else 'unresolved'
            if (job/'metrics.json').exists():
                metrics=read(job/'metrics.json')
                if metrics.get('usage') is not None:
                    paper['extractor']={'provider':'openai','model':metrics.get('model',MODEL),'reasoning':metrics['reasoning']}
            targets={}
            if success:
                for entry in row['entries']:
                    entry=deepcopy(entry);entry['references'][0]['paper_id']=paper['id']
                    data,target=reconcile_entry(data,entry,fingerprints=fingerprints)
                    targets[entry['id']]=target
                # Deduplicate associations when multiple local entries canonicalize
                # to the same slot; their paper-specific evidence stays attached.
                models={}
                for annotation in row['annotations']:
                    target=targets[annotation['local_id']]
                    item=models.setdefault(target,{'entry_id':target,'problems':[],'mechanisms':[]})
                    for kind in ('problems','mechanisms'):
                        for link in annotation[kind]:
                            if link not in item[kind]:item[kind].append(link)
                links['papers'][paper['id']]={'arxiv':paper['arxiv'],'extractor':paper.get('extractor'),
                    'coverage':row['coverage'],'quality':row['quality'],'models':list(models.values())}
            row['entry_ids']=sorted(set(targets.values()))
        validate(data, _specification_cache=_INTAKE_SPECIFICATION_CACHE)
        # Check the complete presentation, without rerunning derived physics for
        # every catalogue entry. Those results are calculated by the site build.
        from .build import main_data
        if any(r.get('entries') for r in rows):
            main_data(data, include_properties=False,
                      _specification_cache=_INTAKE_SPECIFICATION_CACHE)
        write_json(source,data)
        write_json(path_for(source),links)
        for row in rows:
            job=Path(batch)/'jobs'/job_id(row['paper']['arxiv'])
            receipt={k:v for k,v in row.items() if k not in ('entries','annotations','infrastructure')}
            receipt['state']='ingested' if row['state']=='ready' else row['state']
            receipt['finished']=now()
            write_json(job/'state.json',receipt)
            compact(job)
            (job/'intake.json').unlink(missing_ok=True)


def status(directory):
    directory=Path(directory)
    if not (directory/'config.json').exists():return {'phase':'not_started'}
    config=read(directory/'config.json')
    states=Counter();usage=Counter();running=[];measured=0;confidence=Counter();flagged=0
    for job in (directory/'jobs').iterdir():
        if not (job/'state.json').exists():continue
        s=read(job/'state.json');states[s['state']]+=1
        q=s.get('quality') or quality_assessment(s)
        confidence[q.get('confidence') or 'not_reported']+=1
        flagged+=bool(q.get('needs_followup'))
        if s['state']=='running':running.append(job.name)
        if (job/'metrics.json').exists():
            m=read(job/'metrics.json')
            if m.get('usage') is not None:usage.update(m['usage']);measured+=1
    old=read(directory/'status.json') if (directory/'status.json').exists() else {}
    return {**old,'papers':config['papers'],'counts':dict(states),'running_jobs':running,
            'usage':dict(usage),'measured_attempts':measured,'updated':now(),
            'model':config['model'],'reasoning':config['reasoning'],'workers':config['workers'],
            'confidence_counts':dict(confidence),'flagged_papers':flagged}


def run(manifest_path, directory, *, execute=False, resume=False, workers=16, reasoning='medium',
        timeout=900, executable=DEFAULT_EXECUTABLE, corpus=CORPUS, source=SOURCE, max_papers=None, upgrade_quality=False):
    manifest_path,directory,corpus,source=map(lambda p:Path(p).resolve(),(manifest_path,directory,corpus,source))
    papers=read(manifest_path)['papers']
    if len({base_id(p['arxiv']) for p in papers})!=len(papers):raise ValueError('Duplicate paper base IDs')
    if not 1<=workers<=16 or timeout<=0 or reasoning not in ('low','medium','high','xhigh','max') or (max_papers is not None and max_papers<1):raise ValueError('Invalid settings')
    instructions=context();definitions=taxonomies()
    config={'schema_version':'joint-luna-run-2','quality_protocol':'extraction-quality-1','manifest':str(manifest_path),'manifest_sha256':digest(manifest_path.read_bytes()),
        'context_sha256':digest(instructions.encode()),'taxonomies_sha256':digest(json.dumps(definitions,sort_keys=True).encode()),
        'runner_sha256':digest(Path(__file__).read_bytes()),'papers':len(papers),'model':MODEL,'reasoning':reasoning,
        'workers':workers,'timeout':timeout,'executable':str(executable),'corpus':str(corpus),'source':str(source),
        'max_papers':max_papers}
    if not execute:return {'dry_run':True,**config}
    check_worker(executable)
    if directory.exists() and not resume:raise ValueError('Run exists; inspect and use --resume')
    directory.mkdir(parents=True,exist_ok=True);(directory/'jobs').mkdir(exist_ok=True)
    with exclusive_lock(directory/'run.lock'):
        if (directory/'config.json').exists():
            old=read(directory/'config.json')
            if old!=config:
                if resume and upgrade_quality and old.get('schema_version')=='joint-luna-run-1':
                    allowed={'schema_version','quality_protocol','runner_sha256'}
                    if {k:v for k,v in old.items() if k not in allowed}!={k:v for k,v in config.items() if k not in allowed}:
                        raise ValueError('Quality upgrade cannot change models, manifests or operational settings')
                    write_json(directory/'pre-quality-config.json',old)
                    write_json(directory/'config.json',config)
                    write_json(directory/'response.schema.json',response_schema())
                    (directory/'quality-instructions.txt').write_text(JOINT_INSTRUCTIONS)
                    old=config
                # The bounded smoke run can continue with the same manifest,
                # model and prompt without repeating its first paid attempts.
                if old!=config and not (resume and old.get('max_papers') and max_papers is None and
                        {k:v for k,v in old.items() if k!='max_papers'}=={k:v for k,v in config.items() if k!='max_papers'}):
                    raise ValueError('Frozen run settings changed')
                if old!=config:
                    write_json(directory/'bounded-pilot.json',old)
                    write_json(directory/'config.json',config)
        else:
            write_json(directory/'config.json',config);write_json(directory/'response.schema.json',response_schema())
            (directory/'instructions.txt').write_text(instructions);write_json(directory/'taxonomies.json',definitions)
        enqueue(papers,corpus)
        # Recovery never invokes a model again: replay validated deltas, or
        # revalidate a completed response whose intake had not yet begun.
        for paper in papers:
            paper={**paper,'id':paper.get('id','arxiv-'+job_id(paper['arxiv']).replace('.','-'))}
            job=directory/'jobs'/job_id(paper['arxiv'])
            if (job/'intake.json').exists():
                intake(directory,[read(job/'intake.json')],source)
            elif (job/'state.json').exists() and read(job/'state.json')['state']=='running':
                if (job/'result.json').exists():
                    body,_=read_source(paper['arxiv'],corpus)
                    try:
                        result=read(job/'result.json');entries,annotations=validate_response(paper,result,body,definitions)
                        intake(directory,[{'state':'ready','paper':paper,'entries':entries,'annotations':annotations,
                            'coverage':result['coverage'],'outcome':result['outcome'],'reason':result['reason'],
                            'result_sha256':digest((job/'result.json').read_bytes())}],source)
                        continue
                    except ValueError:pass
                intake(directory,[{'state':'interrupted','paper':paper,'reason':'Interrupted attempt retained; no automatic retry'}],source)
        active={};scheduled=0;stop_reason=None;last_status=0;waiting_count=0
        terminating=Event()
        previous_signals={sig:signal.signal(sig,lambda *_:terminating.set()) for sig in (signal.SIGTERM,signal.SIGINT)}
        def checkpoint(phase):
            value=status(directory);value.update(phase=phase,pid=os.getpid(),reason=stop_reason,awaiting_sources=waiting_count,
                                                 scheduled_this_invocation=scheduled)
            transfer=corpus/'transfer-state.json'
            if transfer.exists():value['source_downloader']=read(transfer)
            write_json(directory/'status.json',value);return value
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while True:
                if (directory/'STOP').exists() or (directory.parent/'STOP').exists():stop_reason='User STOP marker; active workers will drain'
                if terminating.is_set():stop_reason='Termination requested; active workers will drain'
                complete=[]
                for future,job in list(active.items()):
                    if not future.done():continue
                    row=future.result();complete.append(row);del active[future]
                    if row.get('infrastructure'):stop_reason=row['reason']
                if complete:intake(directory,complete,source)
                if max_papers is not None and scheduled>=max_papers:stop_reason='Requested bounded pilot completed'
                waiting_count=0;remaining=0
                known={base_id(p['arxiv']) for p in load(source)['papers']}
                if not stop_reason:
                    for item in papers:
                        if len(active)>=workers:break
                        job=directory/'jobs'/job_id(item['arxiv'])
                        if job in active.values():continue
                        if (job/'state.json').exists() and read(job/'state.json')['state'] in TERMINAL:continue
                        remaining+=1
                        if base_id(item['arxiv']) in known:
                            job.mkdir(exist_ok=True);write_json(job/'state.json',{'state':'already_recorded','paper':item});continue
                        paper={k:item[k] for k in ('arxiv','title','authors')};paper['id']=item.get('id','arxiv-'+job_id(item['arxiv']).replace('.','-'))
                        try:body,provenance=read_source(item['arxiv'],corpus)
                        except AwaitingSource:
                            waiting_count+=1;continue
                        except (ValueError,OSError) as error:
                            job.mkdir(exist_ok=True);intake(directory,[{'state':'source_unavailable','paper':paper,'reason':str(error)}],source);continue
                        active[pool.submit(run_worker,job,paper,body,provenance,instructions,definitions,config)]=job;scheduled+=1
                        if max_papers is not None and scheduled>=max_papers:break
                if time.monotonic()-last_status>15:
                    checkpoint('draining' if stop_reason else ('running' if active else 'waiting_for_sources'));last_status=time.monotonic()
                if not active and (stop_reason or not remaining):break
                if active:wait(active,timeout=2,return_when=FIRST_COMPLETED)
                else:time.sleep(10)
        for sig,handler in previous_signals.items():signal.signal(sig,handler)
        return checkpoint('stopped' if stop_reason else 'completed')


def launch(args):
    directory=Path(args.run_dir).resolve()
    if not args.execute:return run(args.manifest,directory,workers=args.workers,reasoning=args.reasoning,executable=args.codex,corpus=args.corpus,max_papers=args.max_papers)
    # Check the parent launch record as well as the coordinator lock.
    directory.parent.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(directory.parent/(directory.name+'-launch.lock')):
        record=directory.parent/(directory.name+'-process.json')
        if record.exists():
            previous=read(record)
            try:os.kill(previous['pid'],0)
            except ProcessLookupError:pass
            else:raise ValueError('Coordinator already alive; duplicate launch refused')
        if directory.exists():
            if not args.resume:raise ValueError('Run exists; use --resume')
            with exclusive_lock(directory/'run.lock'):pass
        if (directory/'STOP').exists() or (directory.parent/'STOP').exists():raise ValueError('STOP marker present; not launching')
        check_worker(args.codex)
        command=[sys.executable,'-B','-u','-m','bsm_atlas.joint_harvest','run',str(Path(args.manifest).resolve()),
                 '--run-dir',str(directory),'--execute','--workers',str(args.workers),'--reasoning',args.reasoning,
                 '--codex',args.codex,'--corpus',str(Path(args.corpus).resolve())]
        if args.resume:command.append('--resume')
        if getattr(args,'upgrade_quality',False):command.append('--upgrade-quality')
        if args.max_papers:command+=['--max-papers',str(args.max_papers)]
        log_path=directory.parent/(directory.name+'-'+str(time.time_ns())+'.log')
        with log_path.open('w') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        guard=None
        if sys.platform=='darwin':
            guard=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(process.pid)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True).pid
        value={'pid':process.pid,'command':command,'model':MODEL,'reasoning':args.reasoning,'workers':args.workers,
               'log':str(log_path),'idle_sleep_guard_pid':guard,'launched':now()}
        write_json(record,value);return value


def main():
    parser=ArgumentParser(description=__doc__);actions=parser.add_subparsers(dest='action',required=True)
    actions.add_parser('status').add_argument('run_dir')
    for name in ('run','launch'):
        sub=actions.add_parser(name);sub.add_argument('manifest');sub.add_argument('--run-dir',required=True)
        sub.add_argument('--execute',action='store_true');sub.add_argument('--resume',action='store_true')
        sub.add_argument('--upgrade-quality',action='store_true')
        sub.add_argument('--workers',type=int,default=16);sub.add_argument('--reasoning',default='medium')
        sub.add_argument('--codex',default=DEFAULT_EXECUTABLE);sub.add_argument('--corpus',type=Path,default=CORPUS)
        sub.add_argument('--max-papers',type=int)
    args=parser.parse_args()
    if args.action=='status':value=status(args.run_dir)
    elif args.action=='launch':value=launch(args)
    else:value=run(args.manifest,args.run_dir,execute=args.execute,resume=args.resume,workers=args.workers,reasoning=args.reasoning,
                   executable=args.codex,corpus=args.corpus,max_papers=args.max_papers,upgrade_quality=args.upgrade_quality)
    print(json.dumps(value,indent=2))


if __name__=='__main__':main()
