"""Atomic per-phase checkpoints. CSV is a recoverable projection, never the source of truth."""
import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class RunStore:
    def __init__(self, output_csv, settings, sample_loader):
        self.output = Path(output_csv).expanduser().resolve()
        self.directory = self.output.with_name(self.output.name + '.state')
        self.manifest_path = self.directory / 'manifest.json'
        self.records_dir = self.directory / 'questions'
        if self.manifest_path.exists():
            self.manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
            if self.manifest['settings'] != settings:
                raise ValueError('Run settings/code differ from this checkpoint. Use a new --output-csv; existing results are preserved.')
            self.samples = json.loads((self.directory / 'samples.json').read_text(encoding='utf-8'))
            if digest(self.samples) != self.manifest['samples_sha256']:
                raise ValueError('Saved sample snapshot failed its integrity check.')
        else:
            if self.output.exists() or self.directory.exists():
                raise ValueError('Existing output/state has no compatible manifest. It will not be overwritten; choose a new output name.')
            self.samples = sample_loader()
            if len(self.samples) != settings['n_samples']:
                raise ValueError('Sample count does not match the requested experiment.')
            ids = [sample['question_id'] for sample in self.samples]
            if len(set(ids)) != len(ids):
                raise ValueError('Duplicate original question IDs.')
            self.output.parent.mkdir(parents=True, exist_ok=True)
            self.records_dir.mkdir(parents=True)
            self.manifest = {'settings': settings, 'question_ids': ids,
                             'samples_sha256': digest(self.samples), 'runtime_identity': None}
            atomic_json(self.directory / 'samples.json', self.samples)
            atomic_json(self.manifest_path, self.manifest)
        self.ids = set(self.manifest['question_ids'])
        if [s['question_id'] for s in self.samples] != self.manifest['question_ids']:
            raise ValueError('Sample identity/order does not match the manifest.')

    def bind_runtime(self, identity):
        old = self.manifest.get('runtime_identity')
        if old is not None and old != identity:
            raise ValueError('Loaded model/encoder identity differs from the saved run; use a new output filename.')
        if old is None:
            self.manifest['runtime_identity'] = identity
            atomic_json(self.manifest_path, self.manifest)

    def read(self, qid):
        if qid not in self.ids:
            raise ValueError('Unknown question ID.')
        path = self.records_dir / (qid + '.json')
        if not path.exists():
            return {'question_id': qid, 'phases': {}}
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('question_id') != qid:
            raise ValueError('Checkpoint question ID mismatch.')
        return record

    def write(self, record):
        qid = record['question_id']
        if qid not in self.ids:
            raise ValueError('Unknown question ID.')
        atomic_json(self.records_dir / (qid + '.json'), record)

    def completed(self, qid, phase):
        return self.read(qid)['phases'].get(phase, {}).get('status') == 'completed'

    def all_complete(self):
        return all(self.completed(qid, phase) for qid in self.ids for phase in ('standard', 'operadic', 'oc'))
