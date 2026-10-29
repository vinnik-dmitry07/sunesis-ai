'''Check question provenance, evidence links and forecast interpretation.'''

import json
from pathlib import Path
import subprocess
import sys
import unittest

from extract import DEFAULT_DATA, extract


ROOT = Path(__file__).resolve().parents[2]
QUESTION_PATH = Path(__file__).with_name('wd40_questions.json')


class QuestionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(QUESTION_PATH.read_text())
        html = (ROOT / 'index.html').read_text()
        cls.case = json.JSONDecoder().raw_decode(
            html.split('const BUNDLED_CASE=', 1)[1]
        )[0]
        cls.book = json.JSONDecoder().raw_decode(
            html.split('const BUNDLED_BOOK=', 1)[1]
        )[0]

    def test_every_question_has_resolvable_evidence_and_original_basis(self):
        cells = set(self.book['cells'])
        sources = {source['id'] for source in self.case['sources']}
        parents = {parent['id'] for parent in self.data['parents']}
        identifiers = [question['id'] for question in self.data['questions']]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for question in self.data['questions']:
            with self.subTest(question=question['id']):
                self.assertIn(question['parentId'], parents)
                self.assertFalse(set(question['cellIds']) - cells)
                self.assertFalse(set(question['sourceIds']) - sources)
                self.assertTrue(question['cellIds'] or question['sourceIds'])
                self.assertIn('Original FY2025', question['answerBasis'])
                if question['category'] == 'fact':
                    self.assertTrue(question['sourceIds'])

    def test_selected_provenance_matches_downloaded_records(self):
        if not (DEFAULT_DATA / 'questions_merged.jsonl').exists():
            self.skipTest('Run collect.py and extract.py to verify raw provenance')
        records, _ = extract(DEFAULT_DATA)
        lookup = {(row['source'], row['recordId']): row for row in records}
        for question in self.data['questions']:
            provenance = question['benchmark']
            key = (provenance['name'], provenance['recordId'])
            with self.subTest(question=question['id']):
                record = lookup[key]
                self.assertTrue(provenance['adapted'])
                self.assertEqual(provenance['originalQuestion'],
                                 record['originalQuestion'])
                self.assertEqual(provenance['version'],
                                 'sha256:' + record['sourceHash'])
                if provenance['name'] == 'fincausal':
                    self.assertIsNone(provenance['originalQuestion'])
                    self.assertEqual(provenance['originalText'],
                                     record['originalText'])

    def test_forecasts_have_resolution_and_no_invented_track_record(self):
        forecasts = [question for question in self.data['questions']
                     if question['category'] == 'forecast']
        self.assertTrue(forecasts)
        for question in forecasts:
            with self.subTest(question=question['id']):
                self.assertEqual(question['status'], 'unresolved_forecast')
                resolution = question['resolution']
                self.assertTrue(resolution['retrospectiveTemplate'])
                for key in ('metric', 'period', 'threshold', 'source', 'resolveAfter'):
                    self.assertTrue(resolution[key])
                self.assertNotIn('probability', question)

    def test_reported_margin_is_distinguished_from_adjusted_margin(self):
        question = next(item for item in self.data['questions']
                        if item['id'] == 'margin-reported')
        values = {item['cell']: item['value'] for item in self.case['proposals']}
        expected = values['Input sheet!B12'] / values['Input sheet!B11']
        self.assertIn(f'{expected * 100:.4f}%', question['answer'])
        self.assertNotEqual(expected, values['Input sheet!B27'])

    def test_fincausal_and_fintextqa_are_not_misrepresented_as_wd40_qa(self):
        source = next(item for item in self.data['sources']
                      if item['id'] == 'fintextqa')
        self.assertEqual(source['recordCount'], 240)
        self.assertIn('not selected', source['usage'])
        self.assertFalse(any(question['benchmark']['name'] == 'fintextqa'
                             for question in self.data['questions']))

    def test_builder_is_deterministic_with_fixed_snapshots(self):
        manifest = json.loads((DEFAULT_DATA / 'manifest.json').read_text())
        if not all((DEFAULT_DATA / source['localFile']).exists()
                   for source in manifest['sources']
                   if source['status'] == 'available'):
            self.skipTest('Raw source snapshots are required for rebuilding')
        before = QUESTION_PATH.read_bytes()
        builder = Path(__file__).with_name('build_questions.py')
        subprocess.run([sys.executable, str(builder)],
                       check=True, capture_output=True, text=True)
        self.assertEqual(before, QUESTION_PATH.read_bytes())


if __name__ == '__main__':
    unittest.main()
