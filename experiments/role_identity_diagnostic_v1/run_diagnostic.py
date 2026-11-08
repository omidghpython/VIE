"""Read saved pilot artifacts without loading a model or executing attachments."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from role_identity_diagnostic import VERSION, diagnose

MAX_FILE = 16 * 1024 * 1024
MAX_ARCHIVE = 64 * 1024 * 1024


def _json(raw):
    if len(raw) > MAX_FILE:
        raise ValueError('JSON file is too large.')
    return json.loads(raw.decode('utf-8-sig'))


def _saved_records(names, read):
    snapshots = [n for n in names if n.endswith('trees.csv.state/samples.json')]
    if len(snapshots) != 1:
        raise ValueError('Expected exactly one pilot samples snapshot.')
    snapshot = snapshots[0]
    prefix = snapshot[:-len('samples.json')]
    samples = _json(read(snapshot))
    if not isinstance(samples, list):
        raise ValueError('Invalid samples snapshot.')
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError('Invalid sample record.')
        qid, question = sample.get('question_id'), sample.get('question')
        if (not isinstance(qid, str) or not qid or '/' in qid or '\\' in qid
                or qid in {'.', '..'} or qid in seen or not isinstance(question, str)):
            raise ValueError('Invalid or duplicate sample identity.')
        seen.add(qid)
        name = prefix + 'questions/' + qid + '.json'
        if name not in names:
            raise ValueError('Missing saved question record: ' + qid)
        rec = _json(read(name))
        if not isinstance(rec, dict) or rec.get('question_id') != qid:
            raise ValueError('Question identity mismatch.')
        phases = rec.get('phases', {})
        if not isinstance(phases, dict) or not isinstance(phases.get('structure', {}), dict):
            raise ValueError('Invalid phase record.')
        stage = phases.get('structure', {})
        result = stage.get('result') or {}
        if not isinstance(result, dict):
            raise ValueError('Invalid saved result.')
        # ID/answer/context are metadata only, never supplied to the detector.
        yield {'question_id': qid, 'question': question,
               'plan': result.get('plan'),
               'saved_structure_status': stage.get('status', 'missing')}


def read_records(path):
    path = Path(path)
    if path.is_dir():
        names = [f.relative_to(path).as_posix() for f in path.rglob('*.json') if f.is_file()]
        def read(name):
            f = (path / name).resolve()
            if not f.is_relative_to(path.resolve()) or f.stat().st_size > MAX_FILE:
                raise ValueError('Unsafe or oversized input file.')
            return f.read_bytes()
        return list(_saved_records(names, read))
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                raise ValueError('Duplicate archive paths.')
            if sum(i.file_size for i in infos) > MAX_ARCHIVE:
                raise ValueError('Archive is too large.')
            for i in infos:
                if (PurePosixPath(i.filename).is_absolute() or '..' in PurePosixPath(i.filename).parts
                        or '\\' in i.filename or i.file_size > MAX_FILE):
                    raise ValueError('Unsafe or oversized archive member.')
            # Only parse outer saved JSON; do not extract or execute anything.
            return list(_saved_records(names, z.read))
    data = _json(path.read_bytes())
    data = [data] if isinstance(data, dict) else data
    if not isinstance(data, list) or any(not isinstance(x, dict) or 'question' not in x or 'plan' not in x for x in data):
        raise ValueError('JSON must contain question/plan pairs.')
    return data


def build_report(records):
    rows = []
    for i, record in enumerate(records, 1):
        rows.append({'index': i, 'question_id': record.get('question_id'),
                     'question': record['question'],
                     'saved_structure_status': record.get('saved_structure_status'),
                     'diagnostic': diagnose(record['question'], record['plan'])})
    return {'diagnostic_version': VERSION, 'advisory_only': True, 'model_calls': 0,
            'meaning': 'No automatic acceptance, rejection or repair; no_violation_found is scoped to recognized role patterns.',
            'counts': dict(Counter(r['diagnostic']['status'] for r in rows)), 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Pilot result ZIP/folder or JSON question/plan pairs')
    parser.add_argument('--output', type=Path, default=Path('role_identity_report.json'))
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Input and output must be different paths.')
    if args.input.is_dir() and args.output.resolve().is_relative_to(args.input.resolve()):
        parser.error('Write the report outside the input folder to preserve saved results.')
    report = build_report(read_records(args.input))
    if args.input.is_file():
        report['input_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['counts'], ensure_ascii=False))
    print('Saved:', args.output)


if __name__ == '__main__':
    main()
