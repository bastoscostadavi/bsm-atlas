"""Tool-free extraction of model inventories, without the annotation layer."""
from copy import deepcopy
import json
import os
import signal
import subprocess
import time

from .catalogue import ROOT, write_json
from .extraction_quality import assessment
from .harvest import (RESULT_SCHEMA, context, prompt, extracted_entries,
                      check_prompt_size, worker_command, event_usage, digest)
from .joint_harvest import read, now, schema_check

SCOPE = 'entries'
INSTRUCTIONS = '''
MODEL INVENTORY OUTPUT CONTRACT
Read the full usable paper and extract all eligible complete gauge-matter
inventories under the supplied atlas conventions. Review model entries only.
Do not assess problems, mechanisms, applications or taxonomy associations.
Return outcome (entries/skip/retry), reason, coverage
(full_text/partial_text/unusable), confidence (high/medium/low),
uncertainty_reason, and entries. Each entry has exactly id, name,
specification_json and nonempty locators. Include no annotation fields or
quotations for application claims. Identify source sections/equations/tables
in the inventory locators. Medium/low confidence requires a concrete reason
about the model inventory. Missing model assignments require retry rather
than invented charges, multiplicities, representations or scalar reality.

When the paper explicitly inherits the SM or MSSM with the same gauge algebra,
use specification_json encoding {"reference_spectrum":"R_SM","additions":[...]}
or {"reference_spectrum":"R_MSSM","additions":[...]} instead of retranscribing
the inherited inventory. The recipe has exactly those two keys. Code copies
the supplied reference spectrum exactly, then adds the stated matter rows.
Use reference factor keys colour, weak_L, hypercharge and the reference's
integer hypercharge normalization. Do not include inherited rows again in
additions. The unextended SM is excluded; a full MSSM benchmark uses R_MSSM
with empty additions. An altered algebra or inherited charge assignment needs
the complete conventional specification. A recipe never supplies facts absent
from the paper. Source locators must establish explicit inheritance.
'''


def response_schema():
    schema = deepcopy(RESULT_SCHEMA)
    fields = {'coverage': {'type': 'string', 'enum': ['full_text', 'partial_text', 'unusable']},
              'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
              'uncertainty_reason': {'type': 'string'}}
    schema['properties'].update(fields)
    schema['required'].extend(fields)
    return schema


def assemble(paper, body, instructions):
    numbered = '\n'.join(f'L{i:06d}: {line}' for i, line in enumerate(body.splitlines(), 1))
    bibliography = {k: paper[k] for k in ('id', 'arxiv', 'title', 'authors') if k in paper}
    message = prompt(bibliography, numbered, instructions+'\n\n'+INSTRUCTIONS)
    check_prompt_size(message)
    return message


def validate_response(paper, result, *, legacy=False):
    """Legacy paid responses can retain their inventory without using annotations."""
    if legacy:
        result = deepcopy(result)
        for entry in result.get('entries', []):
            if isinstance(entry, dict):
                entry.pop('problems', None)
                entry.pop('mechanisms', None)
    schema_check(result, response_schema())
    if result['confidence'] in ('medium', 'low') and not result['uncertainty_reason'].strip():
        raise ValueError('Medium/low confidence requires a concrete inventory uncertainty reason')
    plain = {key: deepcopy(result[key]) for key in ('outcome', 'reason', 'entries')}
    for entry in plain['entries']:
        specification = json.loads(entry['specification_json'])
        if isinstance(specification, dict) and 'reference_spectrum' in specification:
            if (set(specification) != {'reference_spectrum', 'additions'}
                    or specification['reference_spectrum'] not in ('R_SM', 'R_MSSM')
                    or not isinstance(specification['additions'], list)):
                raise ValueError('Invalid reference-spectrum recipe')
            reference = deepcopy(read(ROOT/'atlas/reference_spectra.json')
                                 [specification['reference_spectrum']]['specification'])
            reference['matter'].extend(specification['additions'])
            entry['specification_json'] = json.dumps(reference)
    entries = extracted_entries(paper, plain)
    if result['coverage'] == 'unusable' and entries:
        raise ValueError('Unusable text cannot establish model inventories')
    if len({entry['id'] for entry in entries}) != len(entries):
        raise ValueError('Repeated local model ID')
    return entries


def inventory_quality(row):
    quality = deepcopy(row.get('quality') or assessment(row))
    quality['automatic_flags'] = [flag for flag in quality['automatic_flags']
        if not flag.startswith('evidence:') and flag != 'unclear_association']
    quality['needs_followup'] = bool(quality['automatic_flags'])
    return quality


def run_worker(job, paper, body, provenance, instructions, config):
    job.mkdir(parents=True, exist_ok=True)
    write_json(job/'source.json', provenance)
    write_json(job/'state.json', {'state': 'running', 'scope': SCOPE, 'started': now(), 'paper': paper})
    metrics = {'provider': 'openai', 'model': config['model'], 'reasoning': config['reasoning'],
               'scope': SCOPE, 'usage': None}
    started, process = time.monotonic(), None
    try:
        message = assemble(paper, body, instructions)
        metrics.update(prompt_chars=len(message), prompt_bytes=len(message.encode()))
        (job/'prompt.txt').write_text(message)
        command = worker_command(config['executable'], job, job.parent.parent/'response.schema.json',
                                 config['model'], config['reasoning'])
        command[-1:-1] = ['-c', 'model_context_window=500000', '-c', 'model_auto_compact_token_limit=475000']
        with (job/'events.jsonl').open('w') as stdout, (job/'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(command, cwd=job, stdin=subprocess.PIPE, stdout=stdout,
                stderr=stderr, text=True, encoding='utf-8', start_new_session=True)
            try:
                process.communicate(message, timeout=config['timeout'])
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        if process.returncode:
            diagnostic = (job/'stderr.txt').read_text(errors='replace')[-1500:]
            for line in (job/'events.jsonl').read_text(errors='replace').splitlines():
                try:
                    event = json.loads(line)
                    if event.get('type') in ('error', 'turn.failed'):
                        diagnostic = str(event.get('message', event.get('error', event)))[:1500]
                except ValueError:
                    pass
            raise RuntimeError('Worker exited '+str(process.returncode)+': '+diagnostic)
        result = read(job/'result.json')
        try:
            entries = validate_response(paper, result)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            row = {'state': 'invalid', 'reason': str(error), 'paper': paper, 'infrastructure': False}
            row['quality'] = assessment(row, result)
            return row
        row = {key: result[key] for key in ('outcome', 'coverage', 'reason', 'confidence', 'uncertainty_reason')}
        row.update(state='retry' if result['outcome'] == 'retry' else 'ready', scope=SCOPE,
                   paper=paper, entries=entries, result_sha256=digest((job/'result.json').read_bytes()),
                   infrastructure=False)
        row['quality'] = assessment(row, result)
        return row
    except subprocess.TimeoutExpired as error:
        row = {'state': 'retry', 'category': 'worker_timeout', 'reason': str(error),
               'paper': paper, 'infrastructure': False}
        row['quality'] = assessment(row)
        return row
    except Exception as error:
        row = {'state': 'retry', 'reason': str(error), 'paper': paper,
               'infrastructure': process is not None}
        row['quality'] = assessment(row)
        return row
    finally:
        if (job/'events.jsonl').exists():
            metrics['usage'] = event_usage(job/'events.jsonl')
        metrics.update(elapsed_seconds=round(time.monotonic()-started, 3), finished=now())
        write_json(job/'metrics.json', metrics)
