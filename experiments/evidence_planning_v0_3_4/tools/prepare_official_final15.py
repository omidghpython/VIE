"""Download the original HotpotQA dev file; reproduce baseline seed-42 sampling.
No inference. No mirror fallback. Never rewrite a prepared/used evaluation set.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planning_lab.common import ROOT, atomic_json, digest, file_digest, question_digest, read_json, write_jsonl
from planning_lab.dataset import CONDITIONS, context_sentences, select_evidence, support_pairs
from hotpotqa_operadic_rag.data import context_passages, select_balanced

SEED = 42
COUNTS = {'bridge': 8, 'comparison': 7}
SOURCE = 'http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json'
SOURCE_SHA = '4e9ecb5c8d3b719f624d66b60f8d56bf227f03914f5f0753d6fa1b359d7104ea'
SOURCE_BYTES = 46320117
SOURCE_COUNT = 7405
SELECTION_ID = 'official-hotpotqa-validation15-seed42-v1'
CHECKSUM_REFERENCE = 'https://raw.githubusercontent.com/huggingface/datasets/1.18.0/datasets/hotpot_qa/dataset_infos.json'
GENERATED = ['data/final15_questions.jsonl','private/final15_labels.jsonl',
             'private/final15_original_records.json','data/final15_manifest.json']


def validate_source(raw):
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Not the pinned original HotpotQA distractor dev JSON (SHA256/size mismatch).')
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != SOURCE_COUNT:
        raise ValueError('Expected all 7405 original validation records.')
    return rows


def obtain_source(path=None):
    if path is not None:
        raw = Path(path).read_bytes()
        return validate_source(raw), 'user_supplied_original_file_verified_by_pinned_SHA256'
    cache = ROOT/'dataset_cache/hotpot_dev_distractor_v1.json'
    if cache.exists():
        return validate_source(cache.read_bytes()), 'verified_original_cache'
    errors = []
    for url in [SOURCE.replace('http:', 'https:'), SOURCE]:
        try:
            print('[DATA] Downloading original HotpotQA:', url, flush=True)
            with urllib.request.urlopen(url, timeout=60) as response:
                raw = response.read()
            rows = validate_source(raw)
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix('.download')
            tmp.write_bytes(raw); tmp.replace(cache)
            return rows, url
        except Exception as exc:
            errors.append(f'{url}: {type(exc).__name__}: {exc}')
    raise RuntimeError('Original dataset download failed; no substitute selected.\n'+'\n'.join(errors)+
                       '\nRetry later or use --source PATH_TO_ORIGINAL_JSON; its checksum must match.')


def select_records(rows, exposure, development):
    ids = set(exposure['question_ids']) | {r['question_id'] for r in development}
    hashes = set(exposure['question_hashes']) | {r['question_sha256'] for r in development}
    pools = {k: [] for k in COUNTS}
    seen = set()
    for row in rows:
        qid = row.get('_id', row.get('id'))
        if not isinstance(qid, str) or qid in seen:
            raise ValueError('Missing/duplicate dataset ID')
        seen.add(qid)
        if row.get('type') not in pools or not isinstance(row.get('question'), str):
            raise ValueError('Invalid source question/type')
        if qid in ids or question_digest(row['question']) in hashes:
            continue
        pools[row['type']].append(row)
    selected = []
    for kind, count in COUNTS.items():
        pool = sorted(pools[kind], key=lambda r: r.get('_id', r.get('id')))
        random.Random(SEED).shuffle(pool)
        if len(pool) < count:
            raise ValueError('Not enough unexposed '+kind+' questions')
        selected.extend(pool[:count])
    random.Random(SEED).shuffle(selected)
    if len({question_digest(r['question']) for r in selected}) != 15:
        raise ValueError('Selected questions have duplicate normalized text; no silent resampling.')
    for row in selected:
        context_passages(row['context'])
        evidence = context_sentences(row)
        if not set(support_pairs(row)) <= {(e['title'],e['sentence_id']) for e in evidence}:
            raise ValueError('Supporting fact outside original context')
    return selected, sum(map(len,pools.values()))


def check_original40(rows):
    # Same native sort/shuffle/select procedure used by the original baseline.
    reproduced = select_balanced(rows, 40, SEED)
    original = read_json(ROOT/'private/original_samples.json')
    if [r['question_id'] for r in reproduced] != [r.get('question_id',r.get('id',r.get('_id'))) for r in original]:
        raise ValueError('Official source does not reproduce the original 40 IDs/order; investigate, do not substitute.')
    for a,b in zip(reproduced,original):
        if (a['question'] != b['question'] or a['answer'] != b['answer'] or
            context_sentences(a) != context_sentences(b) or support_pairs(a) != support_pairs(b)):
            raise ValueError('Original 40 content differs from source; stop for provenance review.')


def materialize(selected, eligible, exposure, registry, obtained_via, target):
    public, labels, registration = [], [], []
    for order, sample in enumerate(selected, 1):
        qid = sample.get('_id', sample.get('id'))
        evidence, gold = context_sentences(sample), support_pairs(sample)
        states = []
        for condition in CONDITIONS:
            visible = select_evidence(evidence, gold, condition)
            cid = digest([qid, condition, SELECTION_ID])[:24]
            states.append(dict(case_id=cid,evidence=visible))
            covered = len(set(gold) & {(e['title'],e['sentence_id']) for e in visible})
            labels.append(dict(case_id=cid,source_question_id=qid,order=order,condition=condition,
                answer=sample['answer'],supporting_facts=gold,
                visible_gold_coverage=covered/len(set(gold)) if gold else None,
                reference_action=None,acceptable_targets=None,semantic_review='pending',
                warning='Independent sufficiency/action adjudication required.'))
        public.append(dict(question_id=qid,question=sample['question'],question_type=sample['type'],split='heldout',states=states))
        registration.append(dict(question_id=qid,question_sha256=question_digest(sample['question']),
            type=sample['type'],public_record_sha256=digest(public[-1])))
    registry = dict(registry,heldout=registration)
    manifest = dict(schema_version=1,role='heldout',selection_id=SELECTION_ID,question_count=15,
        types=COUNTS,state_count=75,question_ids=[q['question_id'] for q in public],
        public_records_sha256=digest(public),labels_sha256=digest(labels),originals_sha256=digest(selected),
        registry_sha256=digest(registration),known_exposure_sha256=digest(exposure),source_url=SOURCE,
        source_file_sha256=SOURCE_SHA,source_file_bytes=SOURCE_BYTES,source_pool_records=SOURCE_COUNT,
        eligible_pool_records=eligible,obtained_via=obtained_via,checksum_reference=CHECKSUM_REFERENCE,
        selection=dict(method='Baseline sort IDs, Random(seed).shuffle per type, select, shuffle combined',seed=SEED,counts=COUNTS),
        original40_reproduced=True,overlap_count=0,model_calls_at_selection=0,
        novelty_scope='Unseen in known project exposures; no claim about model pretraining.',
        final_run_status='not_run',independent_semantic_labels='pending')
    write_jsonl(target/'data/final15_questions.jsonl',public)
    write_jsonl(target/'private/final15_labels.jsonl',labels)
    atomic_json(target/'private/final15_original_records.json',selected)
    atomic_json(target/'data/split_registry.json',registry)
    atomic_json(target/'data/final15_manifest.json',manifest)
    return manifest


def prepare(source=None):
    package_path = ROOT/'PACKAGE_MANIFEST.json'
    package = read_json(package_path)
    for name, expected in package['files'].items():
        if file_digest(ROOT/name) != expected:
            raise ValueError('Package file changed: '+name)
    if (ROOT/'data/final15_manifest.json').exists():
        from planning_lab.final15 import load_final15
        _, manifest = load_final15(check_private=True)
        if manifest['selection_id'] != SELECTION_ID:
            raise ValueError('Another cohort exists; use a clean release directory.')
        print('[DATA] Existing official cohort verified; no rewrite, resampling or usage reset.')
        return manifest
    if (ROOT/'data/final15_usage.json').exists() or any((ROOT/p).exists() for p in GENERATED):
        raise ValueError('Existing usage or partial cohort: preserve this directory and prepare in a clean copy.')
    rows, obtained = obtain_source(source)
    check_original40(rows)
    registry = read_json(ROOT/'data/split_registry.json')
    exposure = read_json(ROOT/'provenance/known_exposure_registry.json')
    selected, eligible = select_records(rows,exposure,registry['development'])
    # All construction/validation precedes publishing any selected cohort files.
    with tempfile.TemporaryDirectory(dir=ROOT,prefix='.cohort-stage-') as td:
        staging = Path(td)
        manifest = materialize(selected,eligible,exposure,registry,obtained,staging)
        for name in GENERATED+['data/split_registry.json']:
            dest = ROOT/name; dest.parent.mkdir(parents=True,exist_ok=True)
            (staging/name).replace(dest)
            package['files'][name] = file_digest(dest)
        package['official_final15_prepared'] = True
        atomic_json(package_path,package)
    from planning_lab.final15 import load_final15
    load_final15(check_private=True)
    print('[DATA] READY: 15 original questions, seed=42, 8 bridge + 7 comparison, overlap=0. No model calls.')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Optional original JSON, verified against published SHA256')
    args=parser.parse_args()
    try:
        m=prepare(args.source)
        print(json.dumps({k:m[k] for k in ['selection_id','question_count','types','source_pool_records','overlap_count']},indent=2))
    except Exception as exc:
        print(f'PREPARATION FAILED: {type(exc).__name__}: {exc}',file=sys.stderr)
        sys.exit(1)
