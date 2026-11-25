from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'baseline'
if str(BASELINE) not in sys.path:
    sys.path.insert(0, str(BASELINE))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(canonical(row) + '\n')


def question_digest(question):
    return digest(re.sub(r'\s+', ' ', question.casefold()).strip())


def source_identity():
    paths = sorted((ROOT / 'planning_lab').glob('*.py')) + [ROOT / 'run.py']
    return digest({str(p.relative_to(ROOT)): file_digest(p) for p in paths})


def verify_baseline():
    identity = read_json(ROOT / 'provenance/baseline_identity.json')
    for row in identity['unchanged_files']:
        if file_digest(ROOT / row['path']) != row['sha256']:
            raise ValueError('Frozen baseline changed: ' + row['path'])
    for name, key in [('max4_baseline.zip', 'baseline_zip_sha256'), ('max4_results.zip', 'results_zip_sha256')]:
        if file_digest(ROOT / 'provenance' / name) != identity[key]:
            raise ValueError('Frozen source archive changed: ' + name)
    return identity
