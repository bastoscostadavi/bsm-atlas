"""Catalogue script cache tokens follow served content, including --check."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bsm_atlas import build


HTML='''<html><head>
<link rel="stylesheet" href="field-catalogue.css?v=keep-css">
<script src="field-matrix.js?v=keep-matrix" defer></script>
<script src="field-catalogue-data.js?v=old-data" defer></script>
<script src="field-catalogue.js?v=old-app" defer></script>
</head></html>'''
ASSETS={'field-catalogue-data.js':b'window.FIELD_CATALOGUE = {};\n',
        'field-catalogue.js':b'window.app = 1;\n'}


class BuildAssets(unittest.TestCase):
    def test_content_changes_refresh_only_the_matching_script_token(self):
        first=build.version_script_assets(HTML,ASSETS)
        self.assertEqual(build.version_script_assets(first,ASSETS),first)
        for name,content in ASSETS.items():
            token=sha256(content).hexdigest()[:16]
            self.assertIn(name+'?v='+token,first)
            changed={**ASSETS,name:content+b'// changed\n'}
            new_token=sha256(changed[name]).hexdigest()[:16]
            self.assertEqual(build.version_script_assets(first,changed),first.replace(token,new_token))
        self.assertIn('field-catalogue.css?v=keep-css',first)
        self.assertIn('field-matrix.js?v=keep-matrix',first)

    def test_parses_script_attributes_queries_and_comments(self):
        html='''<!-- <script src="field-catalogue.js?v=comment"></script> -->
<script data-src="field-catalogue.js?v=decoy" defer src='./field-catalogue.js?mode=exact&amp;v=old#init'></script>
<script src=field-catalogue-data.js></script>'''
        result=build.version_script_assets(html,ASSETS)
        self.assertIn('<!-- <script src="field-catalogue.js?v=comment"></script> -->',result)
        self.assertIn('data-src="field-catalogue.js?v=decoy"',result)
        self.assertIn('src="./field-catalogue.js?mode=exact&amp;v='+sha256(ASSETS['field-catalogue.js']).hexdigest()[:16]+'#init"',result)
        self.assertIn('src="field-catalogue-data.js?v='+sha256(ASSETS['field-catalogue-data.js']).hexdigest()[:16]+'"',result)

    def test_requires_exactly_one_actual_local_reference(self):
        bad=[HTML.replace('field-catalogue.js?v=old-app','missing.js'),
             HTML+'<script src="field-catalogue.js"></script>',
             HTML.replace('src="field-catalogue.js?v=old-app"','src="field-catalogue.js" src="field-catalogue.js?v=old-app"'),
             HTML.replace('field-catalogue.js?v=old-app','https://example.com/field-catalogue.js')]
        for html in bad:
            with self.subTest(html=html):
                with self.assertRaises(ValueError):build.version_script_assets(html,ASSETS)

    def test_build_versions_new_data_and_check_rejects_stale_tokens_without_writing(self):
        data={'version':'test-one','entries':[],'papers':[],'cores':[],
              'semisimpleAlgebras':[],'fullAlgebras':[],'counts':{}}
        with tempfile.TemporaryDirectory() as directory,redirect_stdout(StringIO()):
            root=Path(directory);(root/'atlas').mkdir();(root/'website/downloads').mkdir(parents=True)
            for name in ['catalogue.json','entry.schema.json','catalogue.schema.json']:
                (root/'atlas'/name).write_text('{}\n')
            (root/'atlas/schema.sql').write_text('CREATE TABLE metadata (key TEXT PRIMARY KEY,value TEXT);\n')
            index=root/'website/index.html';index.write_text(HTML)
            script=root/'website/field-catalogue.js';script.write_bytes(ASSETS['field-catalogue.js'])
            with patch.object(build,'ROOT',root):
                build.write_outputs(data)
                data_script=root/'website/field-catalogue-data.js'
                self.assertIn('field-catalogue-data.js?v='+sha256(data_script.read_bytes()).hexdigest()[:16],index.read_text())
                build.write_outputs(data,check=True)
                prior=index.read_text();script.write_bytes(ASSETS['field-catalogue.js']+b'// changed\n')
                with self.assertRaisesRegex(ValueError,'Stale generated file: website/index.html'):
                    build.write_outputs(data,check=True)
                self.assertEqual(index.read_text(),prior)
                data['version']='test-two';build.write_outputs(data)
                self.assertIn('field-catalogue-data.js?v='+sha256(data_script.read_bytes()).hexdigest()[:16],index.read_text())
                self.assertIn('field-catalogue.js?v='+sha256(script.read_bytes()).hexdigest()[:16],index.read_text())
                build.write_outputs(data,check=True)


if __name__=='__main__':unittest.main()
