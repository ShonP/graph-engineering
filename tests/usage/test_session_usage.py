import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('session_usage', Path(__file__).resolve().parents[2] / 'scripts/session_usage.py')
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)

class UsageTests(unittest.TestCase):
    def test_stream_duplicates_do_not_double_bill_and_content_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            row = {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': 'same', 'model': 'model', 'content': 'secret sentinel', 'usage': {'input_tokens': 20, 'output_tokens': 2}}}
            path = Path(directory) / 'session.jsonl'
            first = json.dumps(row)
            row['message']['usage']['output_tokens'] = 8
            path.write_text(first + '\n' + json.dumps(row) + '\ninvalid')
            result = usage.aggregate(Path(directory), usage.instant('2026-09-28T00:00:00Z'), usage.instant('2026-09-29T00:00:00Z'))
            self.assertEqual(result['unique_requests'], 1)
            self.assertEqual(result['groups'][0]['output_tokens'], 8)
            self.assertNotIn('secret sentinel', json.dumps(result))
            self.assertEqual(result['malformed_rows'], 1)

    def test_invalid_metadata_is_counted_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [
                {'type': 'assistant', 'timestamp': 9},
                {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': [], 'model': 'model'}},
                {'type': 'assistant', 'timestamp': '2026-09-28T10:00:00Z', 'message': {'id': 'id', 'model': []}},
            ]
            (Path(directory) / 'bad.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
            result = usage.aggregate(Path(directory), usage.instant('2026-09-28T00:00:00Z'), usage.instant('2026-09-29T00:00:00Z'))
            self.assertEqual(result['unique_requests'], 0)
            self.assertEqual(result['malformed_rows'], 3)

    def test_timezone_is_required(self):
        with self.assertRaises(ValueError):
            usage.instant('2026-09-28T00:00:00')

if __name__ == '__main__':
    unittest.main()
