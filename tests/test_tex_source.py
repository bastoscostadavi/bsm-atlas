import gzip
import io
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

from bsm_atlas import tex_source


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as output:
        for name, text in files.items():
            body = text.encode() if isinstance(text, str) else text
            info = tarfile.TarInfo(name)
            info.size = len(body)
            output.addfile(info, io.BytesIO(body))
    return stream.getvalue()


class TexSourceTests(unittest.TestCase):
    def test_single_and_gzipped_tex_preserve_math_and_escaped_percent(self):
        source = (r'\documentclass{article}' '\n'
                  r'\newcommand{\rep}[1]{\mathbf{#1}} % not mathematical content' '\n'
                  r'\begin{document}A 20\% rate, $SU(3)\times SU(2)$.' '\n'
                  r'\begin{equation}\psi\sim(\bar{\rep{3}},2;-1)\end{equation}' '\n'
                  r'\verb|% literal| \cite{a,b} % comment' '\n'
                  r'\end{document}')
        for body in (source.encode(), gzip.compress(source.encode())):
            cleaned = tex_source.clean_tex(body)
            self.assertIn(r'20\%', cleaned)
            self.assertIn(r'\mathbf{#1}', cleaned)
            self.assertIn(r'\bar{\rep{3}}', cleaned)
            self.assertIn(r'\verb|% literal|', cleaned)
            self.assertIn(r'\cite{a,b}', cleaned)
            self.assertNotIn('not mathematical content', cleaned)
            self.assertNotIn('% comment', cleaned)

    def test_nested_inputs_nonstandard_extensions_and_local_definitions(self):
        files = {
            'paper/main.tex': r'\documentclass{local}\usepackage{defs}\input{body.main}',
            'paper/local.cls': r'\newcommand{\gsm}{SU(3)\times SU(2)\times U(1)}',
            'paper/defs.sty': r'\newcommand{\f}[1]{\mathbf{#1}}',
            'paper/body.main': r'\begin{document}\input{sub/fields.pre}\end{document}',
            'paper/sub/fields.pre': r'\begin{table}$(\f3,\f2;1)$\caption{Fields}\end{table}',
            'paper/unused.tex': 'UNUSED DRAFT WITHOUT A MAIN MARKER',
            'paper/figure.pdf': b'%PDF-1.5\x00 binary',
        }
        cleaned, raw, report = tex_source.prepare_tex(archive(files))
        self.assertEqual(report['main_file'], 'paper/main.tex')
        self.assertIn('paper/sub/fields.pre', report['included_files'])
        self.assertIn(r'\gsm', cleaned)
        self.assertIn(r'\mathbf{#1}', cleaned)
        self.assertIn(r'\caption{Fields}', cleaned)
        self.assertNotIn('UNUSED DRAFT', cleaned)
        self.assertIn('UNUSED DRAFT', raw)
        self.assertNotIn('binary', raw)

    def test_omits_bibliography_and_graphics_but_preserves_captions(self):
        source = (r'\documentclass{article}\begin{document}\cite{keep}'
                  r'\begin{figure}\includegraphics[width=2in]{plot.pdf}'
                  r'\begin{tikzpicture}\draw(0,0)--(1,1);\end{tikzpicture}'
                  r'\caption{A scalar in $(1,2;3)$.}\label{fig:scalar}\end{figure}'
                  r'\begin{thebibliography}{9}\bibitem{keep}Hundreds of references.'
                  r'\end{thebibliography}\appendix More field details.\end{document}')
        cleaned = tex_source.clean_tex(source.encode())
        self.assertNotIn(r'\draw', cleaned)
        self.assertNotIn('Hundreds of references', cleaned)
        self.assertNotIn(r'\bibitem', cleaned)
        self.assertIn(r'\cite{keep}', cleaned)
        self.assertIn(r'\caption{A scalar in $(1,2;3)$.}', cleaned)
        self.assertIn(r'\label{fig:scalar}', cleaned)
        self.assertIn('More field details', cleaned)
        self.assertIn('[OMITTED: graphic plot.pdf]', cleaned)
        self.assertIn('[OMITTED: bibliography]', cleaned)

    def test_legacy_bibliography_aliases_preserve_following_appendix(self):
        for environment in ('references', 'references*', 'biblist', 'mcitethebibliography'):
            text = (r'\documentclass{article}\begin{document}Matter table'
                    + '\\begin{' + environment + '}' + r'\bibitem{a}REFERENCE ONLY'
                    + '\\end{' + environment + '}'
                    + r'\appendix CHARGE TABLE $(3,2;1)$\end{document}')
            cleaned = tex_source.clean_tex(text.encode())
            self.assertIn('CHARGE TABLE $(3,2;1)$', cleaned)
            self.assertNotIn('REFERENCE ONLY', cleaned)

    def test_package_internals_preserved_without_host_tex_interpretation(self):
        files = {'main.tex': r'\documentclass{local}\usepackage{fields}\begin{document}$\rep$ FIELD TABLE\end{document}',
                 'local.cls': r'\input{fleqn.clo}\IfFileExists{external.sty}{\RequirePackage{external}}{}\def~{\space}',
                 'fields.sty': r'\def\rep{(3,2;1)}\input{definitions.tex}',
                 'definitions.tex': r'\newcommand{\charge}{7}',
                 'unused.sty': r'\begin{verbatim}BROKEN UNUSED PACKAGE'}
        cleaned, _, report = tex_source.prepare_tex(archive(files))
        self.assertIn(r'\def\rep{(3,2;1)}', cleaned)
        self.assertIn(r'\newcommand{\charge}{7}', cleaned)
        self.assertIn('FIELD TABLE', cleaned)
        self.assertIn('LOCAL TEX DEFINITIONS (unexecuted): local.cls', cleaned)
        self.assertNotIn('BROKEN UNUSED', cleaned)
        self.assertIn('definitions.tex', report['included_files'])
        self.assertEqual(report['cleaner_version'], 2)
        with self.assertRaisesRegex(ValueError, 'Missing TeX dependency'):
            tex_source.clean_tex(archive({'main.tex': files['main.tex'],
                                         'fields.sty': r'\input{missing-matter.tex}'}))

    def test_standard_graphics_input_does_not_require_distribution_file(self):
        for target in ('psfig', 'epsf.tex', 'BoxedEPS.tex'):
            text = (r'\documentclass{article}\input{' + target + '}'
                    + r'\begin{document}\begin{table}CHARGES $q=1$\end{table}\end{document}')
            cleaned = tex_source.clean_tex(text.encode())
            self.assertIn('CHARGES $q=1$', cleaned)
            self.assertIn('external graphics/typesetting input', cleaned)
        with self.assertRaisesRegex(ValueError, 'Missing TeX dependency'):
            tex_source.clean_tex(br'\documentclass{article}\input{field-table}\begin{document}BODY\end{document}')

    def test_file_existence_inputs_follow_local_files_and_explicit_fallback(self):
        main = (r'\documentclass{article}\begin{document}'
                r'\InputIfFileExists{fields.tex}{BEFORE}{WRONG}'
                r'\IfFileExists{fields.tex}{PRESENT}{ABSENT}'
                r'\InputIfFileExists{optional.tex}{}{EXPLICIT FALLBACK}'
                r' AFTER\end{document}')
        cleaned = tex_source.clean_tex(archive({'main.tex':main,'fields.tex':'SCALAR $(1,2;3)$'}))
        for token in ('BEFORE','SCALAR $(1,2;3)$','PRESENT','EXPLICIT FALLBACK','AFTER'):
            self.assertIn(token, cleaned)
        self.assertLess(cleaned.index('BEFORE'),cleaned.index('SCALAR'))
        self.assertNotIn('WRONG',cleaned);self.assertNotIn('ABSENT',cleaned)
        with self.assertRaisesRegex(ValueError,'Dynamic or unsupported'):
            tex_source.clean_tex(main.replace('fields.tex',r'\dynamic').encode())

    def test_missing_input_and_dynamic_input_fail_closed(self):
        for command in (r'\input{missing}', r'\input{\sectionfile}',
                        r'\includeonly{one}', r'\input |"touch /tmp/no"',
                        r'\newcommand{\load}[1]{\input{#1}}\load{body}',
                        r'\InputIfFileExists{fields}{}{}'):
            source = r'\documentclass{article}\begin{document}' + command + r'\end{document}'
            with self.subTest(command=command), self.assertRaises(ValueError):
                tex_source.clean_tex(source.encode())

    def test_content_after_document_end_is_not_added(self):
        cleaned = tex_source.clean_tex(archive({
            'main.tex': r'\documentclass{article}\input{body}\input{missing-unused-draft}',
            'body.tex': r'\begin{document}FIELD INVENTORY\end{document}UNUSED CONTENT'}))
        self.assertIn('FIELD INVENTORY', cleaned)
        self.assertNotIn('UNUSED CONTENT', cleaned)

    def test_repeated_dependency_work_is_bounded(self):
        files = {'main.tex': r'\documentclass{article}\input{a}\input{a}',
                 'a.tex': r'\begin{equation}x^2\end{equation}' * 10}
        with patch.object(tex_source, 'MAX_EXPANDED', 700), self.assertRaisesRegex(ValueError, 'bound'):
            tex_source.clean_tex(archive(files))

    def test_literal_false_and_true_conditionals_select_only_active_branches(self):
        source = (r'\documentclass{article}\begin{document}'
                  r'\iffalse OLD MODEL \input{missing}\ifnum1=1 NESTED\else OTHER\fi'
                  r'\else ACTIVE FIELD $(3,2;1)$\fi'
                  r'\iftrue \input{fields}\iffalse HIDDEN\fi\else OLD FIELDS\fi'
                  r'\end{document}')
        cleaned = tex_source.clean_tex(archive({'main.tex': source,
                                               'fields.tex': 'SCALAR REPRESENTATION'}))
        self.assertIn('ACTIVE FIELD $(3,2;1)$', cleaned)
        self.assertIn('SCALAR REPRESENTATION', cleaned)
        for inactive in ('OLD MODEL', 'NESTED', 'OTHER', 'OLD FIELDS', 'HIDDEN'):
            self.assertNotIn(inactive, cleaned)
        for broken in (r'\iffalse never closed', r'\iftrue x\else y\else z\fi'):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                tex_source.clean_tex((r'\documentclass{article}' + broken).encode())

    def test_arxiv_toplevel_metadata_selects_explicit_paper_not_backup(self):
        import json
        files={'main.tex':r'\documentclass{article}\begin{document}CURRENT CHARGES\end{document}',
               'main.tex.bak':r'\documentclass{article}\begin{document}OBSOLETE CHARGES\end{document}',
               '00README.json':json.dumps({'sources':[{'filename':'main.tex','usage':'toplevel'},
                                                         {'filename':'main.tex.bak','usage':'ignore'}]})}
        cleaned,_,report=tex_source.prepare_tex(archive(files))
        self.assertIn('CURRENT CHARGES',cleaned);self.assertNotIn('OBSOLETE',cleaned)
        self.assertEqual(report['main_selection'],'arxiv_toplevel_metadata')
        files['00README.json']=json.dumps({'sources':[{'filename':'missing.tex','usage':'toplevel'}]})
        with self.assertRaisesRegex(ValueError,'missing arXiv top-level'):
            tex_source.prepare_tex(archive(files))

    def test_identical_prepared_roots_can_be_deduplicated_without_guessing(self):
        text=r'\documentclass{article}\begin{document}SAME FIELDS\end{document}'
        cleaned,_,report=tex_source.prepare_tex(archive({'paper.tex':text,'copy.tex':text}))
        self.assertIn('SAME FIELDS',cleaned)
        self.assertEqual(report['main_selection'],'identical_prepared_roots')

    def test_host_package_presence_is_not_inferred_from_archive_absence(self):
        with self.assertRaisesRegex(ValueError,'Unknown host-distribution'):
            tex_source.clean_tex(br'\documentclass{article}\begin{document}\IfFileExists{external.sty}{MODEL A}{MODEL B}\end{document}')

    def test_independent_main_documents_are_ambiguous(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous independent'):
            tex_source.clean_tex(archive({
                'main.tex': r'\documentclass{article}\begin{document}one\end{document}',
                'old.tex': r'\documentclass{article}\begin{document}two\end{document}'}))

    def test_included_begin_document_does_not_create_second_main(self):
        cleaned = tex_source.clean_tex(archive({
            'hq.tex': r'\documentclass{article}\input{Title}\input{Body}',
            'Title.tex': r'\begin{document}Title',
            'Body.tex': r'Model body\end{document}'}))
        self.assertIn('Model body', cleaned)

    def test_unsafe_archive_paths_never_reach_the_filesystem_or_execute(self):
        sentinel = Path('/tmp/bsm-cleaner-must-not-execute')
        source = (r'\documentclass{article}\begin{document}'
                  r'\immediate\write18{touch /tmp/bsm-cleaner-must-not-execute}'
                  r'BODY\end{document}')
        with (patch.object(tarfile.TarFile, 'extract', side_effect=AssertionError('must not extract')),
              patch.object(tarfile.TarFile, 'extractall', side_effect=AssertionError('must not extract'))):
            cleaned = tex_source.clean_tex(archive({'../../never-extract.tex': source}))
        self.assertIn('BODY', cleaned)
        self.assertFalse(sentinel.exists())

    def test_source_limits_are_not_the_final_worker_context_limit(self):
        source = (r'\documentclass{article}\begin{document}' '\n'
                  + '% verbose formatting comments\n' * 70_000
                  + r'$\psi\sim(3,2;1)$\end{document}')
        self.assertGreater(len(source), 1_500_000)
        cleaned = tex_source.clean_tex(source.encode())
        self.assertLess(len(cleaned), 200)
        self.assertIn(r'\psi', cleaned)
        with patch.object(tex_source, 'MAX_EXPANDED', 100), self.assertRaisesRegex(ValueError, 'bound'):
            tex_source.clean_tex(source.encode())
        with patch.object(tex_source, 'MAX_MEMBERS', 1), self.assertRaisesRegex(ValueError, 'bound'):
            tex_source.clean_tex(archive({'main.tex': r'\documentclass{article}', 'extra.tex': 'text'}))

    def test_cached_source_markers_preserve_exact_file_inventory(self):
        cached = ('\nSOURCE FILE: main.tex\n'
                  r'\documentclass{article}\input{body}\input{References}'
                  '\nSOURCE FILE: body.tex\n'
                  r'\begin{document}Fields $\psi$.\end{document}'
                  '\nSOURCE FILE: References.tex\n'
                  r'\begin{thebibliography}{9}\bibitem{a}REF\end{thebibliography}')
        cleaned, raw, report = tex_source.prepare_cached_tex(cached)
        self.assertIn('Fields', cleaned)
        self.assertNotIn('REF', cleaned)
        self.assertIn('REF', raw)
        self.assertEqual(report['main_file'], 'main.tex')
        self.assertEqual(report['cleaner_version'], tex_source.CLEANER_VERSION)

    def test_html_missing_main_cycles_and_malformed_environments_rejected(self):
        for source in (b'<html>Not TeX</html>',
                       br'\documentclass{article}\input{main.tex}',
                       br'\documentclass{article}\begin{picture}drawing'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                tex_source.clean_tex(source)


if __name__ == '__main__':
    unittest.main()
