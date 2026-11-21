"""Source assembly regressions; never invoke TeX, a model, or the network."""
import unittest
from unittest.mock import patch
from bsm_atlas import tex_source_v3 as tex
from tests.test_tex_source import archive


def paper(body):
    return r'\documentclass{article}\begin{document}'+body+r'\end{document}'


class SourceProfileThreeTests(unittest.TestCase):
    def clean(self,files):
        return tex.prepare_tex(archive(files))

    def test_active_char_and_unbraced_definitions_preserve_exact_matter(self):
        body=(r'\catcode`?=\active\def?{\hphantom{+}}'
              r'\renewcommand{\L}\Lag\newcommand\charge\q'
              r'\newenvironment{fields2}{\begin{tabular}{c}}{\end{tabular}}'
              r'\begin{fields2}$?1$, $(3,2;1)$\end{fields2}')
        text,_,_=self.clean({'main.tex':paper(body)})
        for value in (r'\def?{\hphantom{+}}',r'\renewcommand{\L}\Lag',r'$(3,2;1)$'):
            self.assertIn(value,text)

    def test_let_and_newcommand_aliases_are_not_executed_as_document_commands(self):
        body=(r'\let\bm=\bibitem\newcommand{\nc}{\newcommand}'
              r'\nc{\renc}{\renewcommand}\renc{\foo}{7}'
              r'\begin{mcbibliography}{9}\bm{a}REFERENCE ONLY\end{mcbibliography}'
              r'\appendix FIELD TABLE $q=7$')
        text,_,_=self.clean({'main.tex':paper(body)})
        self.assertIn(r'\let\bm=\bibitem',text)
        self.assertNotIn('REFERENCE ONLY',text)
        self.assertIn('FIELD TABLE $q=7$',text)

    def test_comments_inside_include_macros_do_not_load_commented_drafts(self):
        source=paper('\\newcommand{\\load}[1]{\\input{#1}% } ignored brace\n% \\input{missing}\n}\n\\load{fields}')
        text,_,_=self.clean({'main.tex':source,'fields.tex':'ACTUAL FIELD TABLE'})
        self.assertIn('ACTUAL FIELD TABLE',text)

    def test_parameterized_literal_include_wrapper_and_filename_constant(self):
        files={'main.tex':paper(r'\newcommand{\dir}{sections}'
                               r'\newcommand{\load}[1]{\input{\dir/#1}}\load{fields}'),
               'sections/fields.tex':'EXACT MATTER $(3,2;1)$'}
        text,_,p=self.clean(files)
        self.assertIn('EXACT MATTER $(3,2;1)$',text)
        self.assertIn('sections/fields.tex',p['included_files'])
        self.assertEqual(p['literal_include_expansions'],1)
        files['main.tex']=paper(r'\newcommand{\load}[1]{\input{sections/#1}}\load{missing}')
        with self.assertRaisesRegex(ValueError,'Missing TeX dependency'):self.clean(files)

    def test_unused_file_loader_does_not_require_uninvoked_dependencies(self):
        text,_,_=self.clean({'main.tex':paper(r'\newcommand{\unused}[1]{\input{#1}} MATTER TABLE')})
        self.assertIn('MATTER TABLE',text)

    def test_dependency_loader_defined_in_local_package_is_followed(self):
        files={'main.tex':r'\documentclass{article}\usepackage{defs}\begin{document}\load{fields}\end{document}',
               'defs.sty':r'\newcommand{\load}[1]{\input{sections/#1}}',
               'sections/fields.tex':'WEYL $(1,1;0)$'}
        text,_,_=self.clean(files)
        self.assertIn('WEYL $(1,1;0)$',text)

    def test_xparse_literal_include_wrapper(self):
        text,_,_=self.clean({'main.tex':paper(r'\NewDocumentCommand{\load}{m o}{\input{#1}}\load{fields}'),
                            'fields.tex':'SCALAR $(1,2;3)$'})
        self.assertIn('SCALAR $(1,2;3)$',text)

    def test_subimports_dotted_basenames_and_starred_includes(self):
        text,_,p=self.clean({'main.tex':paper(r'\subimport{sections/}{model.main}\include*{end}'),
                            'sections/model.main.tex':r'\input{fields}',
                            'sections/fields.tex':'GAUGE FIELD TABLE',
                            'end.tex':'END OF SPECIFICATION'})
        self.assertIn('GAUGE FIELD TABLE',text);self.assertIn('END OF SPECIFICATION',text)
        self.assertIn('sections/model.main.tex',p['included_files'])

    def test_includeonly_omits_explicitly_excluded_draft(self):
        text,_,_=self.clean({'main.tex':paper(r'\includeonly{model}\include{model}\include{old}'),
                            'model.tex':'CURRENT FIELDS','old.tex':'OBSOLETE FIELDS'})
        self.assertIn('CURRENT FIELDS',text);self.assertNotIn('OBSOLETE FIELDS',text)

    def test_listing_is_retained_literally_without_executing_code(self):
        text,_,_=self.clean({'main.tex':paper(r'\lstinputlisting[caption={Matter inventory}]{fields.yml}'),
                            'fields.yml':'gauge: su(5)\nmatter: [0,0,0,1]\n'})
        self.assertIn('matter: [0,0,0,1]',text)
        self.assertIn('SOURCE FILE (literal listing): fields.yml',text)

    def test_backup_and_explicit_referee_response_are_not_alternative_models(self):
        text,_,p=self.clean({'paper.tex':paper('CURRENT MODEL'),
                            'paper.tex.bak':paper('OBSOLETE MODEL'),
                            'answer.tex':paper('We thank the Referee for careful reading. RESPONSE')})
        self.assertIn('CURRENT MODEL',text)
        self.assertNotIn('OBSOLETE MODEL',text);self.assertNotIn('RESPONSE',text)
        self.assertEqual(len(p['excluded_document_roots']),2)
        with self.assertRaisesRegex(ValueError,'Ambiguous independent'):
            self.clean({'first.tex':paper('MODEL ONE'),'second.tex':paper('MODEL TWO')})

    def test_wrapper_root_assembles_preamble_and_body_instead_of_preamble_alone(self):
        text,_,p=self.clean({'main.tex':r'\input{preamble}\input{body}',
                            'preamble.tex':r'\documentclass{article}\newcommand{\q}{3}',
                            'body.tex':r'\begin{document}MATTER INVENTORY\end{document}'})
        self.assertEqual(p['main_file'],'main.tex')
        self.assertIn('MATTER INVENTORY',text)
        with self.assertRaisesRegex(ValueError,'terminator'):
            self.clean({'preamble.tex':r'\documentclass{article}\newcommand{\q}{3}'})

    def test_latex_dynamic_end_is_not_mistaken_for_plain_tex_terminator(self):
        with self.assertRaisesRegex(ValueError,'end-environment'):
            self.clean({'main.tex':r'\begin{document}\end\unknown LATER MATTER\end{document}'})
        text,_,_=self.clean({'main.tex':r'\documentclass{article}\def\bd{\begin{document}}\def\ed{\end{document}}\bd FIELD TABLE\ed'})
        self.assertIn('FIELD TABLE',text)

    def test_plain_tex_requires_substantial_document_and_stops_at_primitive_end(self):
        source=r'\magnification=1200\centerline{Paper title}'+('PHYSICS BODY $q=1$. '*100)+r'\end'+'\nUNRELATED POSTSCRIPT'
        text,_,p=self.clean({'main.tex':source})
        self.assertIn('PHYSICS BODY',text);self.assertNotIn('UNRELATED POSTSCRIPT',text)
        self.assertEqual(p['main_selection'],'unique_plain_tex_root')
        with self.assertRaises(ValueError):self.clean({'abstract.tex':'abstract '*100+r'\end'})

    def test_expandafter_graphics_and_empty_package_items_leave_equations(self):
        source=(r'\documentclass{article}\usepackage{,bm,}\begin{document}'
                r'\expandafter\includegraphics\expandafter[\rowofthree]{plot.eps}'
                r'\caption{Representation $(3,2;1)$.}\end{document}')
        text,_,_=self.clean({'main.tex':source})
        self.assertIn('Representation $(3,2;1)',text)
        self.assertIn('[OMITTED: graphic plot.eps]',text)

    def test_unknown_conditional_cannot_select_arbitrary_filename_or_loader(self):
        for body in (r'\ifdefined\flag\def\file{one}\else\def\file{two}\fi\input{\file}',
                     r'\ifdefined\flag\def\load{\input{one}}\else\def\load{\input{two}}\fi\load'):
            with self.subTest(body=body),self.assertRaisesRegex(ValueError,'Conditional'):
                self.clean({'main.tex':paper(body),'one.tex':'ONE FIELDS','two.tex':'TWO FIELDS'})
        text,_,_=self.clean({'main.tex':paper(r'\def\file{one}\def\file{two}\input{\file}'),
                            'one.tex':'ONE FIELDS','two.tex':'TWO FIELDS'})
        self.assertIn('TWO FIELDS',text);self.assertNotIn('ONE FIELDS',text)

    def test_brace_conditionals_cannot_hide_or_arbitrarily_select_file_inputs(self):
        for body in (r'\ifthenelse{condition}{\def\file{one}}{\def\file{two}}\input{\file}',
                     r'\ifstrequal{\flag}{yes}{\input{one}}{\input{two}}'):
            with self.subTest(body=body),self.assertRaisesRegex(ValueError,'Conditional|conditional'):
                self.clean({'main.tex':paper(body),'one.tex':'ONE FIELDS','two.tex':'TWO FIELDS'})
        text,_,_=self.clean({'main.tex':paper(r'\ifstrempty{\q}{MATH A}{MATH B} CHARGE TABLE')})
        self.assertIn('CHARGE TABLE',text);self.assertIn('MATH A',text);self.assertIn('MATH B',text)

    def test_ambiguous_custom_environment_dependency_is_not_silently_lost(self):
        with self.assertRaisesRegex(ValueError,'Custom environment'):
            self.clean({'main.tex':paper(r'\newenvironment{fields}{\input{missing}}{}\begin{fields}\end{fields}')})

    def test_cycles_dynamic_dependencies_and_work_bounds_remain_enforced(self):
        for body in (r'\input{\unknown}',r'\newcommand{\load}[1]{\input{#1}}\load{main.tex}'):
            with self.subTest(body=body),self.assertRaises(ValueError):self.clean({'main.tex':paper(body)})
        with patch.object(tex.base,'MAX_EXPANDED',100),self.assertRaisesRegex(ValueError,'bound'):
            self.clean({'main.tex':paper('X'*200)})

    def test_profile_reader_verifies_corpus_bytes_before_assembly(self):
        import tempfile
        from pathlib import Path
        from bsm_atlas import corpus,corpus_queue
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=corpus.paper_dir(root,'2401.00001','v1')
            body=paper('MATTER TABLE $q=1$. '*40).encode()
            corpus._save(target,'2401.00001','v1','single',{'main.tex':body},[],
                         'https://arxiv.org/e-print/2401.00001v1',len(body))
            with patch.object(tex,'_prepare',wraps=tex._prepare) as prepare:
                text,provenance=corpus_queue.read_source('2401.00001v1',root,preparer=prepare)
                self.assertIn('MATTER TABLE',text);self.assertEqual(provenance['cleaner_version'],3)
                self.assertEqual((target/'source/main.tex').read_bytes(),body)
                (target/'source/main.tex').write_bytes(body.replace(b'q=1',b'q=2'))
                with self.assertRaisesRegex(ValueError,'hash mismatch'):
                    corpus_queue.read_source('2401.00001v1',root,preparer=prepare)
                self.assertEqual(prepare.call_count,1)

    def test_unstandardized_bibliography_retains_later_appendix(self):
        text,_,p=self.clean({'main.tex':paper(r'\bibitem{a}Unusual reference list.\appendix CHARGES $q=3$')})
        self.assertIn('CHARGES $q=3$',text)
        self.assertIn('Nonstandard bibliography retained as source',p['preparation_notes'])


if __name__=='__main__':unittest.main()
