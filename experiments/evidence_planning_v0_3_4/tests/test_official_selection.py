"""Synthetic dataset tests only; never consumes real heldout questions."""
import copy
import hashlib
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest
from unittest.mock import patch
from tools import prepare_official_final15 as prep
from planning_lab.common import digest, question_digest, read_json, file_digest
from planning_lab import final15


def synthetic_rows():
    return [dict(_id=f'synthetic-{i:03}',question=f'Invented question {i}?',type='bridge' if i%2 else 'comparison',
        answer='synthetic',supporting_facts=[['Title 0',0]],
        context=[[f'Title {j}',[f'Invented sentence {i}-{j}.']] for j in range(10)]) for i in range(80)]


class OfficialSelectionTests(unittest.TestCase):
    def setUp(self):
        self.rows=synthetic_rows()
        self.exposure={'question_ids':[],'question_hashes':[]}

    def test_baseline_sort_shuffle_algorithm_and_order_independence(self):
        selected,_=prep.select_records(self.rows,self.exposure,[])
        expected=[]
        for kind,count in [('bridge',8),('comparison',7)]:
            pool=sorted([r for r in self.rows if r['type']==kind],key=lambda r:r['_id'])
            random.Random(42).shuffle(pool);expected.extend(pool[:count])
        random.Random(42).shuffle(expected)
        self.assertEqual(selected,expected)
        self.assertEqual(selected,prep.select_records(list(reversed(self.rows)),self.exposure,[])[0])

    def test_exclusion_by_ids_and_normalized_text_and_development(self):
        initial,_=prep.select_records(self.rows,self.exposure,[])
        self.exposure={'question_ids':[initial[0]['_id']], 'question_hashes':[question_digest('  '+initial[1]['question'].upper()+' ')]}
        development=[{'question_id':initial[2]['_id'],'question_sha256':question_digest(initial[2]['question'])}]
        selected,n=prep.select_records(self.rows,self.exposure,development)
        self.assertEqual(n,77)
        self.assertTrue({r['_id'] for r in selected}.isdisjoint(r['_id'] for r in initial[:3]))

    def test_bad_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA256'):prep.validate_source(b'[]')

    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):prep.select_records(self.rows+[self.rows[0]],self.exposure,[])

    def test_insufficient_pool_rejected(self):
        with self.assertRaisesRegex(ValueError,'Not enough'):prep.select_records(self.rows[:10],self.exposure,[])

    def test_gold_outside_context_rejected(self):
        for row in self.rows:row['supporting_facts']=[['Missing',9]]
        with self.assertRaisesRegex(ValueError,'outside'):prep.select_records(self.rows,self.exposure,[])

    def test_original40_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'original 40'):prep.check_original40(self.rows)

    def test_checksum_metadata_matches_constants(self):
        meta=read_json(prep.ROOT/'provenance/official_dataset_infos_v1.18.0.json')['distractor']['download_checksums'][prep.SOURCE]
        self.assertEqual(meta,{'num_bytes':prep.SOURCE_BYTES,'checksum':prep.SOURCE_SHA})

    def test_prepare_idempotence_and_used_marker_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir();(root/'provenance').mkdir()
            (root/'data/split_registry.json').write_text(json.dumps({'development':[],'heldout':[]}))
            (root/'provenance/known_exposure_registry.json').write_text(json.dumps(self.exposure))
            (root/'PACKAGE_MANIFEST.json').write_text(json.dumps({'files':{}}))
            with patch.object(prep,'ROOT',root),patch.object(final15,'ROOT',root),patch.object(prep,'obtain_source',return_value=(self.rows,'SYNTHETIC_TEST_ONLY')),patch.object(prep,'check_original40'):
                m=prep.prepare();self.assertEqual(m['question_count'],15)
                qs,_=final15.load_final15(check_private=True)
                self.assertTrue(all('answer' not in q for q in qs))
                marker=root/'data/final15_usage.json';marker.write_text('{"already_used":true}')
                before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with patch.object(prep,'obtain_source',side_effect=AssertionError('Must not download again')):prep.prepare()
                after={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
                self.assertEqual(before,after)
                data=root/'data/final15_questions.jsonl';data.write_text('tampered')
                with self.assertRaisesRegex(ValueError,'Package file changed'):prep.prepare()

    def test_partial_and_old_usage_block_preparation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            (root/'PACKAGE_MANIFEST.json').write_text('{"files":{}}')
            (root/'data/final15_usage.json').write_text('{}')
            with patch.object(prep,'ROOT',root),patch.object(prep,'obtain_source',side_effect=AssertionError('Should refuse first')):
                with self.assertRaisesRegex(ValueError,'Existing usage'):prep.prepare()


if __name__=='__main__':unittest.main()
