"""Offline regressions for the Luna/Terra review and deferred Sol queue."""
from copy import deepcopy
from pathlib import Path
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from bsm_atlas import entry_review as review
from bsm_atlas.catalogue import ROOT, identity, load, write_json
from bsm_atlas.extraction_quality import assessment
from bsm_atlas.literature import load_links, path_for, preview


class EntryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = review.read(ROOT/'atlas/catalogue.json')
        cls.template = deepcopy(next(e for e in data['entries'] if e['id'] == 'two-higgs-doublets'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'catalogue.json'
        self.paper = {'id': 'luna-paper', 'arxiv': '2401.00001v1', 'title': 'Paper', 'authors': 'A',
                      'extractor': {'provider': 'openai', 'model': review.LUNA, 'reasoning': 'medium'},
                      'extraction_status': 'complete'}
        self.entry = deepcopy(self.template)
        self.entry['references'] = [{'paper_id': self.paper['id'], 'locators': ['Luna section 2']}]
        self.data = {'schema_version': 'bsm-atlas-1', 'papers': [self.paper], 'entries': [self.entry]}
        write_json(self.source, self.data)
        self.links = {'schema_version': 'atlas-literature-links-1', 'papers': {}}
        self.baseline = review.capture(self.data, self.links, self.paper)
        self.job = self.root/'run/jobs/2401.00001v1'
        self.job.mkdir(parents=True)
        write_json(self.job/'baseline.json', self.baseline)

    def row(self, entries=None, **changes):
        row = {'state': 'ready', 'outcome': 'entries', 'coverage': 'full_text', 'reason': 'Source model',
               'confidence': 'high', 'uncertainty_reason': '', 'paper': self.paper,
               'entries': deepcopy(entries if entries is not None else [self.entry]), 'annotations': []}
        row.update(changes)
        row['quality'] = assessment(row)
        return row

    def changed_entry(self):
        entry = deepcopy(self.entry)
        entry.update(id='terra-correction', name='Terra correction')
        entry.pop('aliases', None)
        entry['specification']['matter'][-1]['copies'] += 1
        entry['references'] = [{'paper_id': self.paper['id'], 'locators': ['Terra table 1']}]
        return entry

    def luna_skip(self, confidence='medium'):
        self.data['entries'] = []
        write_json(self.source, self.data)
        receipt = {'arxiv': self.paper['arxiv'], 'extractor': deepcopy(self.paper['extractor']),
                   'coverage': 'full_text', 'models': [],
                   'quality': assessment({'state': 'ingested', 'coverage': 'full_text',
                       'confidence': confidence, 'uncertainty_reason': 'Uncertain model inventory'})}
        self.links['papers'][self.paper['id']] = receipt
        write_json(path_for(self.source), self.links)
        self.baseline = review.capture(self.data, self.links, self.paper)
        return self.job.parent.parent

    def test_confidence_queue_selects_only_unreviewed_luna_skips(self):
        directory = self.luna_skip()
        for number, (confidence, producer, receipt_present) in enumerate([
                ('low', review.LUNA, True), (None, review.LUNA, True),
                ('high', review.LUNA, True), ('medium', 'another-model', True),
                ('medium', review.LUNA, False)], 2):
            paper = deepcopy(self.paper)
            paper.update(id='paper-'+str(number), arxiv=f'2401.0000{number}v1')
            paper['extractor']['model'] = producer
            self.data['papers'].append(paper)
            if receipt_present:
                receipt = deepcopy(self.links['papers'][self.paper['id']])
                receipt.update(arxiv=paper['arxiv'], extractor=paper['extractor'])
                receipt['quality'] = assessment({'confidence': confidence})
                self.links['papers'][paper['id']] = receipt
        write_json(self.source, self.data)
        write_json(path_for(self.source), self.links)
        self.assertEqual(review.candidates(self.data, review.reviews(self.source)), [])
        result = review.queue_confidence(directory, self.source, execute=True)
        self.assertEqual(result['confidence_counts'], {'medium': 1, 'low': 1, 'not_reported': 1})
        manifest = review.read(result['manifest'])
        self.assertEqual(len(manifest['papers']), 3)
        selected = review.candidates(self.data, review.reviews(self.source), directory, self.links)
        self.assertEqual({p['id'] for p in selected}, {self.paper['id'], 'paper-2', 'paper-3'})
        self.assertEqual(review.queue_confidence(directory, self.source)['eligible_papers'], 0)

    def test_confidence_queue_is_frozen_and_changed_receipt_is_not_dispatched(self):
        directory = self.luna_skip()
        review.queue_confidence(directory, self.source, execute=True)
        other = {**deepcopy(self.paper), 'id': 'new-skip', 'arxiv': '2401.00002v1'}
        self.data['papers'].append(other)
        self.links['papers'][other['id']] = {**deepcopy(self.links['papers'][self.paper['id']]),
                                           'arxiv': other['arxiv']}
        self.links['papers'][self.paper['id']]['quality']['confidence'] = 'high'
        self.assertEqual(review.candidates(self.data, review.reviews(self.source), directory, self.links), [])

    def test_confidence_queue_does_not_repeat_terminal_attempt(self):
        directory = self.luna_skip()
        review.queue_confidence(directory, self.source, execute=True)
        write_json(self.job/'state.json', {'state': 'unresolved'})
        self.assertEqual(review.candidates(self.data, review.reviews(self.source), directory, self.links), [])
        self.assertEqual(review.queue_confidence(directory, self.source)['eligible_papers'], 0)

    def test_confidence_no_entry_agreement_checks_paper_and_preserves_luna_receipt(self):
        self.luna_skip()
        record = review.finish(self.job, self.row([], outcome='skip'), self.baseline, self.source)
        self.assertTrue(record['checked'])
        self.assertFalse(record['needs_sol'])
        self.assertEqual(record['entries'], [])
        self.assertEqual(load(self.source)['entries'], [])
        receipt = load_links(path_for(self.source))['papers'][self.paper['id']]
        self.assertEqual(receipt['quality'], self.links['papers'][self.paper['id']]['quality'])
        self.assertEqual(receipt['extractor']['model'], review.LUNA)

    def test_confidence_discovered_inventory_is_kept_unchecked_for_sol(self):
        self.luna_skip()
        record = review.finish(self.job, self.row(), self.baseline, self.source)
        self.assertEqual(record['state'], 'disagreement')
        self.assertFalse(record['checked'])
        self.assertTrue(record['needs_sol'])
        self.assertEqual(load(self.source)['entries'], [self.entry])
        receipt = load_links(path_for(self.source))['papers'][self.paper['id']]
        self.assertEqual(receipt['models'], [])
        self.assertEqual(receipt['extractor']['model'], review.LUNA)

    def test_confidence_changed_luna_receipt_is_not_overwritten(self):
        directory = self.luna_skip()
        review.queue_confidence(directory, self.source, execute=True)
        self.baseline['confidence_selection'] = review.confidence_requests(directory)[self.paper['id']]
        self.links['papers'][self.paper['id']]['coverage'] = 'partial_text'
        write_json(path_for(self.source), self.links)
        record = review.finish(self.job, self.row(), self.baseline, self.source)
        self.assertEqual(record['state'], 'stale_baseline')
        self.assertFalse(record['applied'])
        self.assertEqual(load(self.source)['entries'], [])
        self.assertEqual(load_links(path_for(self.source)), self.links)

    def test_confidence_runner_resume_uses_original_worker_once(self):
        directory = self.luna_skip()
        review.queue_confidence(directory, self.source, execute=True)
        with patch.object(review, 'check_worker'), patch.object(review, 'read_source', return_value=('paper text', {})), \
                patch.object(review, 'run_worker', return_value=self.row([], outcome='skip')) as worker:
            first = review.run(directory, execute=True, workers=1, source=self.source)
            second = review.run(directory, execute=True, workers=1, source=self.source)
        self.assertEqual(first['checked_papers'], 1)
        self.assertEqual(second['awaiting_confidence_review'], 0)
        self.assertEqual(worker.call_count, 1)
        saved = review.read(self.job/'baseline.json')
        self.assertEqual(saved['confidence_selection']['luna_receipt'], self.links['papers'][self.paper['id']])

    def test_agreement_checks_canonical_entry_independent_of_name(self):
        entry = deepcopy(self.entry)
        entry.update(id='another-name', name='Another name')
        record = review.finish(self.job, self.row([entry]), self.baseline, self.source)
        self.assertTrue(record['checked'])
        self.assertTrue(record['entries'][0]['checked'])
        self.assertFalse(record['needs_sol'])
        self.assertFalse(record['needs_terra_retry'])
        self.assertEqual(load(self.source)['entries'][0]['id'], self.entry['id'])
        self.assertEqual(review.candidates(review.read(self.source), review.reviews(self.source)), [])

    def test_disagreement_replaces_luna_and_preserves_superseded_inventory(self):
        changed = self.changed_entry()
        record = review.finish(self.job, self.row([changed]), self.baseline, self.source)
        self.assertEqual(record['state'], 'disagreement')
        self.assertTrue(record['applied'])
        self.assertFalse(record['checked'])
        self.assertFalse(record['entries'][0]['checked'])
        self.assertTrue(record['needs_sol'])
        self.assertFalse(record['needs_terra_retry'])
        self.assertEqual(load(self.source)['entries'], [changed])
        self.assertEqual(review.read(self.job/'baseline.json')['entries'], [self.entry])
        queue = review.status(self.job.parent.parent, self.source, queue=True)
        self.assertEqual(queue['sol_queue_papers'], 1)
        self.assertEqual(queue['sol_queue'][0]['arxiv'], self.paper['arxiv'])

    def test_common_entry_checked_even_when_an_additional_model_disagrees(self):
        record = review.finish(self.job, self.row([self.entry, self.changed_entry()]), self.baseline, self.source)
        self.assertFalse(record['checked'])
        self.assertEqual({e['entry_id']: e['checked'] for e in record['entries']},
                         {self.entry['id']: True, 'terra-correction': False})

    def test_shared_entry_keeps_other_papers_reference(self):
        other = {**self.paper, 'id': 'other', 'arxiv': '2401.00002v1'}
        self.data['papers'].append(other)
        self.data['entries'][0]['references'].append({'paper_id': 'other'})
        write_json(self.source, self.data)
        review.finish(self.job, self.row([self.changed_entry()]), self.baseline, self.source)
        after = load(self.source)
        original = next(e for e in after['entries'] if e['id'] == self.entry['id'])
        self.assertEqual(original['references'], [{'paper_id': 'other'}])
        self.assertEqual(len(after['entries']), 2)

    def test_corrected_specification_cannot_reuse_withdrawn_url(self):
        changed = self.changed_entry()
        changed['id'] = self.entry['id']
        record = review.finish(self.job, self.row([changed]), self.baseline, self.source)
        entry = load(self.source)['entries'][0]
        self.assertNotEqual(entry['id'], self.entry['id'])
        self.assertTrue(entry['id'].startswith(self.entry['id']+'-'))
        self.assertEqual(record['entries'][0]['entry_id'], entry['id'])

    def test_terra_skip_removes_only_luna_paper_inventory_and_queues_deletion(self):
        record = review.finish(self.job, self.row([], outcome='skip'), self.baseline, self.source)
        self.assertTrue(record['applied'])
        self.assertTrue(record['needs_sol'])
        self.assertEqual(load(self.source)['entries'], [])
        self.assertEqual(len(load(self.source)['papers']), 1)

    def test_invalid_or_incomplete_response_preserves_luna_and_is_unchecked(self):
        before = self.source.read_bytes()
        record = review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        self.assertFalse(record['applied'])
        self.assertFalse(record['needs_sol'])
        self.assertTrue(record['needs_terra_retry'])
        self.assertEqual(record['next_pass'], 'terra')
        self.assertEqual(self.source.read_bytes(), before)
        queue = review.status(self.job.parent.parent, self.source, queue=True)
        self.assertEqual(queue['terra_retry_papers'], 1)
        self.assertEqual(queue['sol_queue_papers'], 0)
        self.assertEqual(queue['terra_retry_queue'][0]['arxiv'], self.paper['arxiv'])
        self.assertEqual(queue['sol_queue'], [])

    def test_low_confidence_valid_correction_is_kept_unchecked(self):
        record = review.finish(self.job, self.row([self.changed_entry()], confidence='low',
            uncertainty_reason='Uncertain attribution'), self.baseline, self.source)
        self.assertTrue(record['applied'])
        self.assertFalse(record['checked'])
        self.assertTrue(record['needs_sol'])

    def test_changed_baseline_is_never_overwritten(self):
        self.data['entries'] = [self.changed_entry()]
        write_json(self.source, self.data)
        before = self.source.read_bytes()
        record = review.finish(self.job, self.row(), self.baseline, self.source)
        self.assertEqual(record['state'], 'stale_baseline')
        self.assertFalse(record['applied'])
        self.assertTrue(record['needs_terra_retry'])
        self.assertFalse(record['needs_sol'])
        self.assertEqual(self.source.read_bytes(), before)

    def test_interrupted_commit_replays_without_union_or_paid_retry(self):
        row = self.row([self.changed_entry()])
        real = review.write_json
        def fail_links(path, value):
            if Path(path).name == 'literature_links.json':
                raise OSError('interrupted annotation write')
            return real(path, value)
        with patch.object(review, 'write_json', side_effect=fail_links), self.assertRaises(OSError):
            review.finish(self.job, row, self.baseline, self.source)
        self.assertTrue((self.job/'apply.json').exists())
        saved = review.read(self.job/'apply.json')
        record = review.finish(self.job, saved['row'], saved['baseline'], self.source)
        self.assertEqual(load(self.source)['entries'], [self.changed_entry()])
        self.assertFalse((self.job/'apply.json').exists())
        self.assertEqual(review.finish(self.job, row, self.baseline, self.source), record)

    def test_annotation_disagreement_is_separate_from_inventory_check(self):
        annotation = {'local_id': self.entry['id'], 'problems': [{'term_id': 'dark_matter',
                      'rationale': 'Paper studies it', 'evidence': [], 'reviewReasons': []}], 'mechanisms': []}
        luna = {'arxiv': self.paper['arxiv'], 'extractor': self.paper['extractor'], 'models': [
            {'entry_id': self.entry['id'], 'problems': [], 'mechanisms': []}]}
        self.links['papers'][self.paper['id']] = luna
        write_json(path_for(self.source), self.links)
        self.baseline = review.capture(self.data, self.links, self.paper)
        record = review.finish(self.job, self.row(annotations=[annotation]), self.baseline, self.source)
        self.assertTrue(record['checked'])
        self.assertNotIn('associations_checked', record)
        self.assertNotIn('associations_agree', record)
        self.assertFalse(record['needs_sol'])
        self.assertIsNone(record['next_pass'])
        stored = load_links(path_for(self.source))['papers'][self.paper['id']]
        self.assertEqual(stored['models'], luna['models'])
        self.assertEqual(stored['extractor']['model'], review.LUNA)

    def test_luna_links_for_changed_inventory_are_retained_without_transfer(self):
        luna_model = {'entry_id': self.entry['id'], 'problems': [{'term_id': 'dark_matter',
            'rationale': 'Original Luna claim', 'evidence': [], 'reviewReasons': []}], 'mechanisms': []}
        self.links['papers'][self.paper['id']] = {'arxiv': self.paper['arxiv'],
            'extractor': self.paper['extractor'], 'models': [luna_model]}
        write_json(path_for(self.source), self.links)
        self.baseline = review.capture(self.data, self.links, self.paper)
        review.finish(self.job, self.row([self.changed_entry()]), self.baseline, self.source)
        stored = load_links(path_for(self.source))['papers'][self.paper['id']]
        self.assertEqual(stored['extractor']['model'], review.LUNA)
        self.assertEqual(stored['models'], [])
        self.assertEqual(stored['detached_models'], [{'fingerprint': identity(self.entry['specification'])['fingerprint'],
                                                     'model': luna_model}])

    def test_concurrent_luna_annotation_edit_is_preserved(self):
        luna = {'arxiv': self.paper['arxiv'], 'extractor': self.paper['extractor'], 'models': [
            {'entry_id': self.entry['id'], 'problems': [], 'mechanisms': []}]}
        self.links['papers'][self.paper['id']] = deepcopy(luna)
        self.baseline = review.capture(self.data, self.links, self.paper)
        self.links['papers'][self.paper['id']]['models'][0]['problems'] = [{'term_id': 'dark_matter',
            'rationale': 'Updated by Luna while Terra read the paper', 'evidence': [], 'reviewReasons': []}]
        write_json(path_for(self.source), self.links)
        record = review.finish(self.job, self.row(), self.baseline, self.source)
        self.assertTrue(record['applied'])
        stored = load_links(path_for(self.source))['papers'][self.paper['id']]
        self.assertEqual(stored['models'], self.links['papers'][self.paper['id']]['models'])

    def test_annotation_quality_flags_do_not_prevent_inventory_agreement(self):
        row = self.row()
        row['quality']['automatic_flags'] = ['evidence:quote_found', 'unclear_association']
        row['quality']['needs_followup'] = True
        record = review.finish(self.job, row, self.baseline, self.source)
        self.assertTrue(record['checked'])
        self.assertFalse(record['quality']['needs_followup'])

    def test_review_removes_superseded_frozen_links_but_preserves_other_evidence(self):
        other = {**self.paper, 'id': 'other', 'arxiv': '2401.00002v1'}
        self.data['papers'].append(other)
        self.data['entries'][0]['references'].append({'paper_id': 'other'})
        write_json(self.source, self.data)
        frozen = {'schema_version': 'atlas-literature-baseline-1',
                  'entry_fingerprints': {self.entry['id']: identity(self.entry['specification'])['fingerprint']},
                  'problems': {'problems': [{'id': 'dark_matter'}], 'assessed': [self.entry['id']],
                    'links': {self.entry['id']: {'dark_matter': [{'paperId': self.paper['id']}, {'paperId': 'other'}]}}}}
        baseline_path = self.root/'baseline.json'
        write_json(baseline_path, frozen)
        review.finish(self.job, self.row([], outcome='skip'), self.baseline, self.source)
        result = preview('problems', self.source, baseline_path)
        self.assertEqual(result['links'][self.entry['id']]['dark_matter'], [{'paperId': 'other'}])

    def test_runner_resume_does_not_repeat_completed_worker(self):
        directory = self.root/'coordinator'
        def fake(job, paper, *args):
            return self.row()
        with patch.object(review, 'check_worker'), patch.object(review, 'read_source', return_value=('paper text', {})), \
                patch.object(review, 'run_worker', side_effect=fake) as worker:
            first = review.run(directory, execute=True, workers=1, source=self.source)
            second = review.run(directory, execute=True, workers=1, source=self.source)
        self.assertEqual(first['checked_papers'], 1)
        self.assertEqual(second['phase'], 'completed')
        self.assertEqual(worker.call_count, 1)

    def test_resume_does_not_read_indexed_terminal_metadata(self):
        review.finish(self.job, self.row(), self.baseline, self.source)
        write_json(self.job/'metrics.json', {'usage': {'input_tokens': 10}})
        real_read = review.read
        real_metadata = review.read_metadata

        def unreadable_history(path):
            if Path(path).parent.resolve() == self.job.resolve() and Path(path).name in ('state.json', 'metrics.json'):
                raise TimeoutError('Archived metadata is unavailable')
            return real_read(path)

        def metadata(path, **kwargs):
            if Path(path).parent.resolve() == self.job.resolve() and Path(path).name in ('state.json', 'metrics.json'):
                raise TimeoutError('Archived metadata is unavailable')
            return real_metadata(path, **kwargs)

        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read', side_effect=unreadable_history), \
                patch.object(review, 'read_metadata', side_effect=metadata), \
                patch.object(review, 'status', side_effect=AssertionError('Full history scan')), \
                patch.object(review, 'run_worker') as worker:
            result = review.run(self.job.parent.parent, execute=True, workers=1, source=self.source)
        worker.assert_not_called()
        self.assertEqual(result['checked_papers'], 1)
        self.assertEqual(result['phase'], 'completed')

    def test_unreadable_history_does_not_block_new_review_dispatch(self):
        review.finish(self.job, self.row(), self.baseline, self.source)
        write_json(self.job/'metrics.json', {'usage': {'input_tokens': 10}})
        job, row, _ = self.second_job()
        real_read = review.read
        real_metadata = review.read_metadata

        def unreadable_history(path):
            if Path(path).parent.resolve() == self.job.resolve() and Path(path).name in ('state.json', 'metrics.json'):
                raise TimeoutError('Archived metadata is unavailable')
            return real_read(path)

        def metadata(path, **kwargs):
            if Path(path).parent.resolve() == self.job.resolve() and Path(path).name in ('state.json', 'metrics.json'):
                raise TimeoutError('Archived metadata is unavailable')
            return real_metadata(path, **kwargs)

        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read', side_effect=unreadable_history), \
                patch.object(review, 'read_metadata', side_effect=metadata), \
                patch.object(review, 'status', side_effect=AssertionError('Full history scan')), \
                patch.object(review, 'read_source', return_value=('text', {})), \
                patch.object(review, 'run_worker', return_value=row) as worker:
            result = review.run(self.job.parent.parent, execute=True, workers=1, source=self.source)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(worker.call_args.args[0], job.resolve())
        self.assertEqual(result['reviewed_papers'], 2)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Requires Unix named pipes')
    def test_saved_metadata_read_has_a_real_wall_time_limit(self):
        fifo = self.root/'blocked-metadata.json'
        os.mkfifo(fifo)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            review.read_metadata(fifo, timeout=.15)
        self.assertLess(time.monotonic()-started, 3)

    def test_saved_metadata_snapshot_preserves_original_bytes_and_timestamp(self):
        path = self.root/'metadata.json'
        value = {'state': 'agreement', 'usage': {'input_tokens': 7}}
        write_json(path, value)
        before, stamp = path.read_bytes(), path.stat().st_mtime_ns
        self.assertEqual(review.read_metadata(path), value)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_bounded_file_snapshot_preserves_binary_bytes(self):
        path = self.root/'fingerprint-input.bin'
        raw = bytes(range(256))*10
        path.write_bytes(raw)
        self.assertEqual(review.read_saved_bytes(path), raw)

    def test_bounded_source_preparation_preserves_text_and_provenance(self):
        from bsm_atlas.corpus import paper_dir
        from bsm_atlas.corpus_queue import read_source as direct_read_source
        from bsm_atlas.tex_source_v3 import _prepare
        corpus = self.root/'corpus'
        paper = paper_dir(corpus, '2401.00001', 'v1')
        (paper/'source').mkdir(parents=True)
        raw = (r'\documentclass{article}\begin{document}\section{Model}'+'\n'+
               ('We specify a complete gauge and matter inventory with scalar and fermion multiplets.\n'*200)+
               r'\end{document}').encode()
        (paper/'source/main.tex').write_bytes(raw)
        write_json(paper/'meta.json', {'arxiv': '2401.00001', 'version': 'v1', 'status': 'ok',
                   'files': [{'path': 'main.tex', 'bytes': len(raw),
                              'sha256': review.sha256(raw).hexdigest()}]})
        self.assertEqual(review.read_source(self.paper['arxiv'], corpus),
                         direct_read_source(self.paper['arxiv'], corpus, preparer=_prepare))

    def test_terra_assembles_luna_profile_three_sources_and_checks_original_hashes(self):
        from bsm_atlas.corpus import paper_dir
        from bsm_atlas.corpus_queue import read_source as direct_read_source
        from bsm_atlas.tex_source_v3 import _prepare
        corpus = self.root/'corpus'
        paper = paper_dir(corpus, '2401.00001', 'v1')
        (paper/'source').mkdir(parents=True)
        sources = {'main.tex': (r'\documentclass{article}\newcommand{\load}[1]{\input{#1}}'
                    r'\begin{document}\load{matter}\end{document}').encode(),
                   'matter.tex': ('Matter table: a Weyl fermion has charge $q=7$.\n'*40).encode()}
        for name, raw in sources.items():
            (paper/'source'/name).write_bytes(raw)
        write_json(paper/'meta.json', {'arxiv': '2401.00001', 'version': 'v1', 'status': 'ok',
            'files': [{'path': name, 'bytes': len(raw), 'sha256': review.sha256(raw).hexdigest()}
                      for name, raw in sources.items()]})
        with self.assertRaisesRegex(ValueError, 'macro-mediated'):
            direct_read_source(self.paper['arxiv'], corpus)
        text, provenance = review.read_source(self.paper['arxiv'], corpus)
        self.assertIn('charge $q=7$', text)
        self.assertEqual(provenance['cleaner_version'], 3)
        self.assertEqual((text, provenance),
                         direct_read_source(self.paper['arxiv'], corpus, preparer=_prepare))
        (paper/'source/matter.tex').write_bytes(sources['matter.tex'].replace(b'q=7', b'q=9'))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            review.read_source(self.paper['arxiv'], corpus)
        self.assertFalse((self.job/'state.json').exists())

    def test_source_preparation_policy_is_frozen_before_dispatch(self):
        directory = self.job.parent.parent
        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read_source', return_value=('text', {})), \
                patch.object(review, 'run_worker', return_value=self.row()) as worker:
            review.run(directory, execute=True, workers=1, source=self.source)
            frozen = review.read(directory/'config.json')
            self.assertEqual(frozen['source_preparation_profile'], 'tex-v3')
            self.assertEqual(frozen['cleaner_version'], 3)
            changed = {**review.source_preparation_policy(), 'source_preparation_sha256': 'changed'}
            with patch.object(review, 'source_preparation_policy', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'Frozen review configuration changed'):
                    review.run(directory, execute=True, workers=1, source=self.source)
        self.assertEqual(worker.call_count, 1)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'Requires Unix named pipes')
    def test_stalled_source_read_is_bounded_without_starting_a_model(self):
        from bsm_atlas.corpus import paper_dir
        corpus = self.root/'corpus'
        paper = paper_dir(corpus, '2401.00001', 'v1')
        paper.mkdir(parents=True)
        os.mkfifo(paper/'meta.json')
        started = time.monotonic()
        with self.assertRaises(review.AwaitingSource):
            review.read_source(self.paper['arxiv'], corpus, timeout=.2)
        self.assertLess(time.monotonic()-started, 3)
        self.assertFalse((self.job/'state.json').exists())

    def test_unavailable_paper_source_does_not_block_other_reviews(self):
        job, row, _ = self.second_job()

        def source(identifier, *_):
            if identifier == self.paper['arxiv']:
                raise review.AwaitingSource('Temporarily unavailable')
            return 'text', {}

        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read_source', side_effect=source), \
                patch.object(review, 'run_worker', return_value=row) as worker:
            result = review.run(self.job.parent.parent, execute=True, workers=1, source=self.source)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(worker.call_args.args[0], job.resolve())
        self.assertEqual(result['reviewed_papers'], 1)
        self.assertEqual(result['awaiting_first_review'], 1)
        self.assertFalse((self.job/'state.json').exists())

    def test_usage_timeout_preserves_paid_result_journal(self):
        row = self.row()
        ledger = review.UsageLedger()
        with patch.object(review, 'run_worker', return_value=row), \
                patch.object(review, 'read_metadata', side_effect=TimeoutError('Metrics unavailable')):
            returned = review.durable_worker(self.job, self.paper, 'text', {}, '', {},
                                             self.baseline, accounting=ledger)
        self.assertEqual(returned, row)
        self.assertEqual(review.read(self.job/'apply.json'), {'row': row, 'baseline': self.baseline})
        self.assertEqual(ledger.snapshot()['usage_missing_since_launch'], 1)

    def test_new_call_usage_is_counted_once_without_rescanning_history(self):
        ledger = review.UsageLedger({'usage': {'input_tokens': 100}, 'updated': 'cached'})
        with patch.object(review, 'read_metadata', return_value={'usage': {'input_tokens': 7}}) as metadata:
            ledger.capture(self.job)
            ledger.capture(self.job)
        self.assertEqual(metadata.call_count, 1)
        self.assertEqual(ledger.snapshot()['usage'], {'input_tokens': 107})
        self.assertEqual(ledger.snapshot()['usage_since_launch'], {'input_tokens': 7})
        self.assertTrue(ledger.snapshot()['usage_is_lower_bound'])

    def test_live_status_uses_only_the_existing_snapshot_and_queue_state(self):
        review.finish(self.job, self.row(), self.baseline, self.source)
        snapshot = (self.data, self.links, review.reviews(self.source))
        queues = {'awaiting_first_review': 3, 'awaiting_confidence_review': 1,
                  'awaiting_requested_terra_retry': 2, 'queue_counts_as_of': 'snapshot'}
        with patch.object(review, 'read', side_effect=AssertionError('Unexpected file read')), \
                patch.object(review, 'read_metadata', side_effect=AssertionError('Unexpected metadata read')), \
                patch.object(review, 'job_directories', side_effect=AssertionError('Unexpected history scan')):
            result = review.live_status(snapshot, queues=queues, active=2, waiting=1,
                                        accounting=review.UsageLedger())
        self.assertEqual(result['reviewed_papers'], 1)
        self.assertEqual(result['checked_papers'], 1)
        self.assertEqual(result['counts'], {'agreement': 1})
        self.assertEqual(result['awaiting_first_review'], 3)
        self.assertEqual(result['results_waiting_apply'], 1)

    def test_bounded_literature_reader_keeps_existing_schema_validation(self):
        from bsm_atlas import literature
        path = self.root/'links.json'
        self.assertEqual(review.load_links(path), literature.load_links(path))
        write_json(path, self.links)
        self.assertEqual(review.load_links(path), literature.load_links(path))
        for data in [{'schema_version': 'invalid', 'papers': {}},
                     {'schema_version': literature.VERSION, 'papers': []},
                     {'schema_version': literature.VERSION, 'papers': {}, 'extra': True}]:
            write_json(path, data)
            with self.assertRaises(ValueError):
                review.load_links(path)
            with self.assertRaises(ValueError):
                literature.load_links(path)

    def second_job(self):
        paper = {**self.paper, 'id': 'second-paper', 'arxiv': '2401.00002v1'}
        self.data = deepcopy(self.data)
        self.data['papers'].append(paper)
        self.data['entries'][0]['references'].append({'paper_id': paper['id']})
        write_json(self.source, self.data)
        baseline = review.capture(self.data, self.links, paper)
        entry = deepcopy(self.entry)
        entry['references'] = [{'paper_id': paper['id']}]
        row = self.row([entry], paper=paper)
        job = self.job.parent/'2401.00002v1'
        job.mkdir()
        write_json(job/'baseline.json', baseline)
        return job, row, baseline

    def test_batch_reconciles_shared_spectrum_and_writes_each_store_once(self):
        second = self.second_job()
        self.baseline = review.capture(self.data, self.links, self.paper)
        with patch.object(review, 'write_json', wraps=write_json) as writes, \
                patch.object(review, 'validate', wraps=review.validate) as validate:
            records = review.finish_batch([(self.job, self.row(), self.baseline), second], self.source)
        self.assertTrue(all(r['checked'] for r in records))
        after = load(self.source)
        self.assertEqual(len(after['entries']), 1)
        self.assertEqual({r['paper_id'] for r in after['entries'][0]['references']},
                         {self.paper['id'], 'second-paper'})
        self.assertEqual(validate.call_count, 1)
        for store in (self.source, path_for(self.source), review.review_path(self.source)):
            self.assertEqual(sum(Path(call.args[0]) == store for call in writes.call_args_list), 1)

    def test_batch_replays_after_each_shared_file_boundary_without_new_calls(self):
        second = self.second_job()
        self.baseline = review.capture(self.data, self.links, self.paper)
        items = [(self.job, self.row([self.changed_entry()]), self.baseline), second]
        initial = self.source.read_bytes()
        for failure in (path_for(self.source), review.review_path(self.source), self.job/'comparison.json'):
            with self.subTest(failure=failure):
                self.source.write_bytes(initial)
                path_for(self.source).unlink(missing_ok=True)
                review.review_path(self.source).unlink(missing_ok=True)
                def fail(path, value):
                    if Path(path) == failure:
                        raise OSError('simulated interrupted batch')
                    return write_json(path, value)
                with patch.object(review, 'write_json', side_effect=fail), self.assertRaises(OSError):
                    review.finish_batch(items, self.source)
                self.assertTrue(all((job/'apply.json').exists() for job, _, _ in items))
                with patch.object(review, 'run_worker') as worker:
                    records = review.finish_batch(items, self.source)
                worker.assert_not_called()
                self.assertEqual([r['state'] for r in records], ['disagreement', 'agreement'])
                self.assertEqual(len(load(self.source)['entries']), 2)
                self.assertFalse(any((job/'apply.json').exists() for job, _, _ in items))

    def test_restore_missing_receipts_preserves_inventory_and_prevents_repeats(self):
        record = review.finish(self.job, self.row([self.changed_entry()]), self.baseline, self.source)
        before = self.source.read_bytes()
        review.review_path(self.source).unlink()
        with patch.object(review, 'run_worker') as worker:
            restored = review.restore_review_receipts(self.job.parent.parent, self.source)
            again = review.restore_review_receipts(self.job.parent.parent, self.source)
        worker.assert_not_called()
        self.assertEqual((restored, again), (1, 0))
        self.assertEqual(review.reviews(self.source)['papers'][self.paper['id']], record)
        self.assertEqual(self.source.read_bytes(), before)

    def test_saved_worker_receipt_survives_before_application(self):
        row = self.row()
        with patch.object(review, 'run_worker', return_value=row):
            review.durable_worker(self.job, self.paper, 'text', {}, '', {}, self.baseline)
        saved = review.read(self.job/'apply.json')
        self.assertEqual(saved, {'row': row, 'baseline': self.baseline})
        write_json(self.job/'state.json', {'state': 'running'})
        state = review.status(self.job.parent.parent, self.source)
        self.assertEqual(state['model_calls_running'], 0)
        self.assertEqual(state['results_waiting_apply'], 1)
        self.assertEqual(state['awaiting_first_review'], 0)

    def test_cached_validation_rechecks_changed_specs_and_reference_constraints(self):
        from bsm_atlas.catalogue import validate
        cache = {}
        validate(self.data, _specification_cache=cache)
        self.assertEqual(len(cache), 1)
        invalid = deepcopy(self.data)
        invalid['entries'][0]['references'] = [{'paper_id': 'unknown'}]
        with self.assertRaises(ValueError):
            validate(invalid, _specification_cache=cache)
        invalid = deepcopy(self.data)
        invalid['entries'][0]['specification']['inventory_complete'] = False
        with self.assertRaises(ValueError):
            validate(invalid, _specification_cache=cache)
        invalid = deepcopy(self.data)
        duplicate = deepcopy(invalid['entries'][0])
        duplicate['id'] = 'duplicate-spectrum'
        invalid['entries'].append(duplicate)
        with self.assertRaises(ValueError):
            validate(invalid, _specification_cache=cache)

    def test_export_checks_are_reused_only_for_unchanged_specifications(self):
        from bsm_atlas import build
        cache = set()
        with patch.object(build, 'main_data', wraps=build.main_data) as export:
            review._validate_export_changes(self.data, {self.paper['id']}, cache)
            review._validate_export_changes(self.data, {self.paper['id']}, cache)
            self.data['entries'][0] = self.changed_entry()
            review._validate_export_changes(self.data, {self.paper['id']}, cache)
        self.assertEqual(export.call_count, 2)

    def test_restart_applies_saved_batch_without_repeating_paid_workers(self):
        second = self.second_job()
        self.baseline = review.capture(self.data, self.links, self.paper)
        items = [(self.job, self.row(), self.baseline), second]
        for job, row, baseline in items:
            write_json(job/'state.json', {'state': 'running', 'paper': baseline['paper']})
            write_json(job/'apply.json', {'row': row, 'baseline': baseline})
        with patch.object(review, 'check_worker'), patch.object(review, 'run_worker') as worker:
            result = review.run(self.job.parent.parent, execute=True, workers=2, source=self.source)
        worker.assert_not_called()
        self.assertEqual(result['reviewed_papers'], 2)
        self.assertEqual(result['pipeline']['recovered_results'], 2)

    def test_worker_slots_refill_before_the_completed_batch_is_applied(self):
        from threading import Event
        self.second_job()
        for index in (3, 4):
            paper = {**self.paper, 'id': f'paper-{index}', 'arxiv': f'2401.0000{index}v1'}
            self.data['papers'].append(paper)
            self.data['entries'][0]['references'].append({'paper_id': paper['id']})
        write_json(self.source, self.data)
        third_started = Event()
        starts = []
        def worker(job, paper, *args):
            starts.append(paper['id'])
            if len(starts) >= 3:
                third_started.set()
            entry = deepcopy(self.entry)
            entry['references'] = [{'paper_id': paper['id']}]
            return self.row([entry], paper=paper)
        real_finish = review.finish_batch
        def finish(items, *args, **kwargs):
            self.assertTrue(third_started.wait(2), 'No replacement worker started before application')
            return real_finish(items, *args, **kwargs)
        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read_source', return_value=('text', {})), \
                patch.object(review, 'run_worker', side_effect=worker), \
                patch.object(review, 'finish_batch', side_effect=finish):
            result = review.run(self.root/'refill-run', execute=True, workers=2, source=self.source)
        self.assertEqual(result['reviewed_papers'], 4)
        self.assertEqual(len(starts), 4)

    def test_idle_dispatch_refreshes_after_a_writer_adds_new_work(self):
        from threading import Event, Thread
        from bsm_atlas.catalogue import source_lock
        new_data = deepcopy(self.data)
        write_json(self.source, {**self.data, 'entries': []})
        written, release = Event(), Event()
        errors = []

        def add_work():
            try:
                with source_lock(self.source, wait=True):
                    write_json(self.source, new_data)
                    written.set()
                    if not release.wait(5):
                        errors.append('Idle reader never waited for the new source snapshot')
            except Exception as error:
                errors.append(str(error))

        writer = Thread(target=add_work)
        real_snapshot = review.dispatch_snapshot
        scans = []

        def snapshot(source, *, wait=False):
            if not scans:
                old = real_snapshot(source, wait=wait)
                scans.append('old-empty-snapshot')
                writer.start()
                self.assertTrue(written.wait(5))
                return old
            if wait:
                # A queued blocking reader gets a turn after this writer;
                # repeated nonblocking reads keep seeing its held lock.
                release.set()
            return real_snapshot(source, wait=wait)

        try:
            with patch.object(review, 'check_worker'), \
                    patch.object(review, 'read_source', return_value=('text', {})), \
                    patch.object(review, 'run_worker', return_value=self.row()) as worker, \
                    patch.object(review, 'dispatch_snapshot', side_effect=snapshot):
                result = review.run(self.root/'idle-refresh', execute=True, workers=1, source=self.source)
            self.assertEqual(result['reviewed_papers'], 1)
            self.assertEqual(worker.call_count, 1)
        finally:
            release.set()
            if writer.ident is not None:
                writer.join(5)
        self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])

    def test_dispatch_continues_while_the_writer_holds_the_catalogue_lock(self):
        from threading import Event
        self.data = deepcopy(self.data)
        for index in range(2, 9):
            paper = {**self.paper, 'id': f'paper-{index}', 'arxiv': f'2401.0000{index}v1'}
            self.data['papers'].append(paper)
            self.data['entries'][0]['references'].append({'paper_id': paper['id']})
        write_json(self.source, self.data)
        sufficient_work = Event()
        starts = []
        def worker(job, paper, *args):
            starts.append(paper['id'])
            if len(starts) >= 6:
                sufficient_work.set()
            entry = deepcopy(self.entry)
            entry['references'] = [{'paper_id': paper['id']}]
            return self.row([entry], paper=paper)
        real_finish = review.finish_batch
        def slow_finish(items, *args, **kwargs):
            from bsm_atlas.catalogue import source_lock
            with source_lock(self.source, wait=True):
                self.assertTrue(sufficient_work.wait(5), 'Dispatch stalled behind the shared writer lock')
                self.assertIsNone(review.dispatch_snapshot(self.source))
            return real_finish(items, *args, **kwargs)
        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read_source', return_value=('text', {})), \
                patch.object(review, 'run_worker', side_effect=worker), \
                patch.object(review, 'finish_batch', side_effect=slow_finish):
            result = review.run(self.root/'independent-writer', execute=True, workers=2, source=self.source)
        self.assertEqual(result['reviewed_papers'], 8)
        self.assertEqual(len(starts), 8)

    def prepare_retry(self):
        directory = self.job.parent.parent
        result = review.queue_retries(directory, self.source, execute=True)
        manifest = review.read(Path(result['manifest']))
        request = next(r for r in manifest['papers'] if r['paper_id'] == self.paper['id'])
        job = Path(result['manifest']).parent/'jobs'/review.job_id(self.paper['arxiv'])
        job.mkdir(parents=True)
        previous = review.reviews(self.source)['papers'][self.paper['id']]
        baseline = review.capture(review.read(self.source), load_links(path_for(self.source)), self.paper)
        write_json(job/'previous-review.json', previous)
        write_json(job/'retry.json', request)
        write_json(job/'baseline.json', baseline)
        return job, baseline

    def test_explicit_retry_selects_only_unresolved_once_per_requested_pass(self):
        second = self.second_job()
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        review.finish(second[0], self.row([self.changed_entry()]), second[2], self.source)
        result = review.queue_retries(self.job.parent.parent, self.source, execute=True)
        manifest = review.read(Path(result['manifest']))
        self.assertEqual([r['paper_id'] for r in manifest['papers']], [self.paper['id']])
        self.assertTrue((Path(result['manifest']).parent/'response.schema.json').exists())
        self.assertEqual(review.queue_retries(self.job.parent.parent, self.source)['eligible_papers'], 0)

    def test_successful_retry_checks_inventory_and_preserves_original_attempt(self):
        previous = review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        original_bytes = (self.job/'state.json').read_bytes()
        job, baseline = self.prepare_retry()
        record = review.finish(job, self.row(), baseline, self.source)
        self.assertTrue(record['checked'])
        self.assertEqual(record['previous_jobs'], [str(self.job.resolve())])
        self.assertEqual(review.read(job/'previous-review.json'), previous)
        self.assertEqual((self.job/'state.json').read_bytes(), original_bytes)
        status = review.status(self.job.parent.parent, self.source)
        self.assertEqual(status['reviewed_papers'], 1)
        self.assertEqual(status['checked_papers'], 1)
        self.assertEqual(status['terra_retry_papers'], 0)
        self.assertEqual(status['awaiting_requested_terra_retry'], 0)
        self.assertEqual(status['attempt_counts'], {'unresolved': 1, 'agreement': 1})

    def test_retry_disagreement_keeps_terra_and_enters_sol_queue(self):
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        job, baseline = self.prepare_retry()
        record = review.finish(job, self.row([self.changed_entry()]), baseline, self.source)
        self.assertTrue(record['needs_sol'])
        self.assertFalse(record['needs_terra_retry'])
        self.assertFalse(record['checked'])
        self.assertEqual(load(self.source)['entries'], [self.changed_entry()])

    def test_inconclusive_retry_stays_separate_and_does_not_repeat_automatically(self):
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        job, baseline = self.prepare_retry()
        record = review.finish(job, self.row([], state='retry'), baseline, self.source)
        self.assertTrue(record['needs_terra_retry'])
        self.assertFalse(record['needs_sol'])
        self.assertEqual(review.retry_candidates(self.job.parent.parent, review.read(self.source),
                                                review.reviews(self.source)), [])

    def test_retry_requires_frozen_authorization_for_the_current_unresolved_receipt(self):
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        unauthorized = self.root/'unauthorized'
        unauthorized.mkdir()
        with self.assertRaisesRegex(ValueError, 'explicit retry required'):
            review.finish(unauthorized, self.row(), self.baseline, self.source)
        job, baseline = self.prepare_retry()
        store = review.reviews(self.source)
        store['papers'][self.paper['id']]['reason'] = 'Changed review record'
        write_json(review.review_path(self.source), store)
        with self.assertRaisesRegex(ValueError, 'explicit retry required'):
            review.finish(job, self.row(), baseline, self.source)

    def test_retry_journal_recovers_after_partial_commit_and_preserves_latest_receipt(self):
        old_row = self.row([], state='invalid')
        review.finish(self.job, old_row, self.baseline, self.source)
        job, baseline = self.prepare_retry()
        row = self.row([self.changed_entry()])
        def fail_links(path, value):
            if Path(path) == path_for(self.source):
                raise OSError('interrupted retry commit')
            return write_json(path, value)
        with patch.object(review, 'write_json', side_effect=fail_links), self.assertRaises(OSError):
            review.finish(job, row, baseline, self.source)
        record = review.finish(job, row, baseline, self.source)
        self.assertTrue(record['applied'])
        self.assertEqual(review.finish(job, row, baseline, self.source), record)
        review.finish(self.job, old_row, self.baseline, self.source)
        self.assertEqual(review.reviews(self.source)['papers'][self.paper['id']], record)

    def test_missing_registry_restores_the_latest_retry_without_overwriting_old_jobs(self):
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        job, baseline = self.prepare_retry()
        latest = review.finish(job, self.row(), baseline, self.source)
        review.review_path(self.source).unlink()
        review.restore_review_receipts(self.job.parent.parent, self.source)
        self.assertEqual(review.reviews(self.source)['papers'][self.paper['id']], latest)
        self.assertEqual(review.restore_review_receipts(self.job.parent.parent, self.source), 0)

    def test_runner_retries_once_and_gives_first_reviews_priority_with_shared_slots(self):
        from threading import Lock
        self.second_job()
        review.finish(self.job, self.row([], state='invalid'), self.baseline, self.source)
        directory = self.job.parent.parent
        review.queue_retries(directory, self.source, execute=True)
        calls = []
        lock = Lock()
        def worker(job, paper, *args):
            with lock:
                calls.append(paper['id'])
            entry = deepcopy(self.entry)
            entry['references'] = [{'paper_id': paper['id']}]
            return self.row([entry], paper=paper)
        with patch.object(review, 'check_worker'), \
                patch.object(review, 'read_source', return_value=('text', {})), \
                patch.object(review, 'run_worker', side_effect=worker):
            first = review.run(directory, execute=True, workers=1, source=self.source)
            second = review.run(directory, execute=True, workers=1, source=self.source)
        self.assertEqual(calls, ['second-paper', self.paper['id']])
        self.assertEqual(first['checked_papers'], 2)
        self.assertEqual(second['awaiting_requested_terra_retry'], 0)

    def test_legacy_unresolved_flags_do_not_enter_the_sol_queue(self):
        record = {'state': 'unresolved', 'checked': False, 'associations_checked': False,
                  'needs_sol': True, 'paper': self.paper, 'entries': [], 'job': str(self.job)}
        write_json(review.review_path(self.source),
                   {'schema_version': review.VERSION, 'papers': {self.paper['id']: record}})
        restored = review.reviews(self.source)['papers'][self.paper['id']]
        self.assertFalse(restored['needs_sol'])
        self.assertTrue(restored['needs_terra_retry'])

    def test_disagreement_and_unresolved_queues_are_disjoint(self):
        common = {'checked': False, 'associations_checked': False, 'entries': [], 'job': str(self.job)}
        records = {'a': {**common, 'state': 'unresolved', 'paper': self.paper},
                   'b': {**common, 'state': 'disagreement', 'applied': True, 'inventory_agrees': False,
                         'paper': {**self.paper, 'arxiv': '2401.00002v1'}}}
        write_json(review.review_path(self.source), {'schema_version': review.VERSION, 'papers': records})
        queue = review.status(self.job.parent.parent, self.source, queue=True)
        terra = {r['arxiv'] for r in queue['terra_retry_queue']}
        sol = {r['arxiv'] for r in queue['sol_queue']}
        self.assertEqual(terra, {self.paper['arxiv']})
        self.assertEqual(sol, {'2401.00002v1'})
        self.assertFalse(terra & sol)

    def test_quality_flags_on_matching_inventory_do_not_trigger_sol(self):
        record = review.finish(self.job, self.row(confidence='low',
            uncertainty_reason='Uncertain application evidence'), self.baseline, self.source)
        self.assertTrue(record['applied'])
        self.assertTrue(record['inventory_agrees'])
        self.assertFalse(record['checked'])
        self.assertFalse(record['needs_sol'])
        self.assertFalse(record['needs_terra_retry'])
        self.assertIsNone(record['next_pass'])
        self.assertTrue(record['quality']['needs_followup'])

    def test_sol_queue_contains_exactly_completed_inventory_disagreements(self):
        common = {'checked': False, 'associations_checked': False, 'needs_sol': True,
                  'entries': [], 'job': str(self.job), 'paper': self.paper}
        records = {
            'inventory': {**common, 'state': 'disagreement', 'applied': True, 'inventory_agrees': False},
            'annotations': {**common, 'state': 'agreement', 'applied': True, 'inventory_agrees': True},
            'quality': {**common, 'state': 'agreement', 'applied': True, 'inventory_agrees': True},
            'unresolved': {**common, 'state': 'unresolved', 'applied': False, 'inventory_agrees': False},
            'stale': {**common, 'state': 'stale_baseline', 'applied': False, 'inventory_agrees': False},
        }
        write_json(review.review_path(self.source), {'schema_version': review.VERSION, 'papers': records})
        restored = review.reviews(self.source)['papers']
        self.assertEqual({key for key, value in restored.items() if value['needs_sol']}, {'inventory'})
        self.assertEqual({key for key, value in restored.items() if value['needs_terra_retry']},
                         {'unresolved', 'stale'})


if __name__ == '__main__':
    unittest.main()
