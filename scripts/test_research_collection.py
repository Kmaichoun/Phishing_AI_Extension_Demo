"""Offline tests for publisher provenance and bounded URL-only retrieval."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from train_simple_model import read_published_rows
from collect_research_urls import RangeReader


class CollectionTests(unittest.TestCase):
    def test_dates_provenance_checksum_and_reserved_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = dict(url='https://example.org/?q=test', label='0', source='fixture',
                       observed_at='', time_precision='unknown', publisher_split='external')
            manifest = dict(csv='urls.csv', sources={'fixture':dict(
                url='https://example.org/data', license='Test fixture', attribution='Test only',
                label_evidence='Not a real dataset', time_semantics='Unknown')})
            def write():
                with (root/'urls.csv').open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
                manifest['csv_sha256'] = hashlib.sha256((root/'urls.csv').read_bytes()).hexdigest()
                (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            write()
            self.assertEqual(list(read_published_rows(root/'manifest.json'))[0]['observed_at'], '')
            row.update(observed_at='2025-01-02', time_precision='day', publisher_split='train'); write()
            self.assertEqual(len(list(read_published_rows(root/'manifest.json'))), 1)
            row['publisher_split'] = 'test'; write()
            with self.assertRaises(ValueError): list(read_published_rows(root/'manifest.json'))
            row.update(publisher_split='train', observed_at='2999-01-01'); write()
            with self.assertRaises(ValueError): list(read_published_rows(root/'manifest.json'))
            row.update(time_precision='unknown'); write()
            with self.assertRaises(ValueError): list(read_published_rows(root/'manifest.json'))
            row.update(observed_at=''); write()
            with (root/'urls.csv').open('a') as f: f.write('tampered')
            with self.assertRaises(ValueError): list(read_published_rows(root/'manifest.json'))

    def test_range_reader_rejects_full_download_and_oversize(self):
        stream = RangeReader('https://example.org/dataset.parquet', 50_000_000)
        stream.session.close()
        stream.session = MagicMock()
        response = stream.session.get.return_value.__enter__.return_value
        response.status_code = 200
        with self.assertRaises(ValueError): stream.read(100)
        response.raw.read.assert_not_called()
        with self.assertRaises(ValueError): stream.read(25_000_000)
        stream.seek(30)
        response.status_code = 206
        response.headers = {'Content-Range':'bytes 30-33/50000000'}
        response.raw.read.return_value = b'test'
        self.assertEqual(stream.read(4), b'test')
        self.assertEqual(stream.tell(), 34)
        self.assertEqual(stream.transferred, 4)
        response.headers = {'Content-Range':'bytes 0-3/50000000'}
        with self.assertRaises(ValueError): stream.read(4)


if __name__ == '__main__': unittest.main(verbosity=2)
