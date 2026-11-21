"""Reproducible selection from a data-only public mirror; no model calls or outcome selection."""
import argparse
import hashlib
import io
import json
import pickle
import pickletools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planning_lab.common import ROOT, atomic_json, digest, question_digest, read_json, write_jsonl
from planning_lab.dataset import CONDITIONS, context_sentences, select_evidence, support_pairs

SOURCE = 'https://raw.githubusercontent.com/NotAbleToFindAUsername/HotpotQA_Dataset/6ac268e426770b3c13c84566aaf4b55ce9548352/hotpotqa_distractor_validation.pkl'
SOURCE_SHA = '0d2968ed54b43b0403743de7b2886094943a8938b00908baa728603dcbd8ce64'
SELECTION_SALT = 'VIE-final15-v1-2026-11-21'


class ContainersOnly(pickle.Unpickler):
    def find_class(self, module, name):
        raise ValueError('Only data containers are permitted')
    def persistent_load(self, value):
        raise ValueError('Persistent references are forbidden')


def build(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Mirror bytes do not match the pinned source')
    unsafe = {'GLOBAL','STACK_GLOBAL','REDUCE','NEWOBJ','NEWOBJ_EX','OBJ','INST','BUILD','PERSID','BINPERSID','EXT1','EXT2','EXT4'}
    if any(op.name in unsafe for op, _, _ in pickletools.genops(raw)):
        raise ValueError('Executable object instructions are not allowed')
    columns = ContainersOnly(io.BytesIO(raw)).load()
    records = [{k:v[i] for k,v in columns.items()} for i in range(len(columns['question']))]
    exposure = read_json(ROOT/'provenance/known_exposure_registry.json')
    ids, hashes = set(exposure['question_ids']), set(exposure['question_hashes'])
    registry = read_json(ROOT/'data/split_registry.json')
    ids.update(q['question_id'] for q in registry['development'])
    hashes.update(q['question_sha256'] for q in registry['development'])
    eligible = [s for s in records if s['id'] not in ids and question_digest(s['question']) not in hashes]
    selected = []
    for kind, count in [('bridge',8),('comparison',7)]:
        candidates = sorted((s for s in eligible if s['type'] == kind),
                            key=lambda s: digest([SELECTION_SALT,s['id']]))
        if len(candidates) < count:
            raise ValueError('Not enough eligible records')
        selected.extend(candidates[:count])
    selected.sort(key=lambda s:digest([SELECTION_SALT,s['id'],'order']))
    if len({question_digest(s['question']) for s in selected}) != 15:
        raise ValueError('Duplicate questions in final selection')
    public, labels, registration = [], [], []
    for order, sample in enumerate(selected,1):
        evidence, gold = context_sentences(sample), support_pairs(sample)
        lookup = {(e['title'],e['sentence_id']) for e in evidence}
        if not set(gold) <= lookup:
            raise ValueError('Supporting fact lies outside source context')
        states = []
        for condition in CONDITIONS:
            visible = select_evidence(evidence,gold,condition)
            cid = digest([sample['id'],condition,'final15-v1'])[:24]
            states.append(dict(case_id=cid,evidence=visible))
            covered = len(set(gold) & {(e['title'],e['sentence_id']) for e in visible})
            labels.append(dict(case_id=cid,source_question_id=sample['id'],order=order,
                               condition=condition,answer=sample['answer'],supporting_facts=gold,
                               visible_gold_coverage=covered/len(set(gold)) if gold else None,
                               reference_action=None,acceptable_targets=None,semantic_review='pending',
                               warning='Independent sufficiency/action adjudication is still required.'))
        public.append(dict(question_id=sample['id'],question=sample['question'],
                           question_type=sample['type'],split='heldout',states=states))
        registration.append(dict(question_id=sample['id'],question_sha256=question_digest(sample['question']),
                                 type=sample['type'],public_record_sha256=digest(public[-1])))
    write_jsonl(ROOT/'data/final15_questions.jsonl',public)
    write_jsonl(ROOT/'private/final15_labels.jsonl',labels)
    atomic_json(ROOT/'private/final15_original_records.json',selected)
    registry['heldout'] = registration
    atomic_json(ROOT/'data/split_registry.json',registry)
    manifest = dict(schema_version=1,role='heldout',selection_id='final15-v1',question_count=15,
                    types={'bridge':8,'comparison':7},state_count=75,
                    question_ids=[q['question_id'] for q in public],
                    public_records_sha256=digest(public),labels_sha256=digest(labels),
                    originals_sha256=digest(selected),registry_sha256=digest(registration),
                    known_exposure_sha256=digest(exposure),source_url=SOURCE,source_file_sha256=SOURCE_SHA,
                    source_pool_records=len(records),eligible_pool_records=len(eligible),
                    selection={'method':'stratified SHA256 ranking of IDs, no model outcomes',
                               'salt':SELECTION_SALT,'counts':{'bridge':8,'comparison':7}},
                    source_note='Public 200-row mirror of HotpotQA distractor validation; original host was unreachable.',
                    overlap_check='IDs and normalized text hashes against all available known project exposures',
                    overlap_count=0,model_calls_at_selection=0,
                    novelty_scope='Unseen in available project development records; not a pretraining-exclusion claim.',
                    final_run_status='not_run',independent_semantic_labels='pending')
    atomic_json(ROOT/'data/final15_manifest.json',manifest)
    return {k:manifest[k] for k in ['question_count','types','state_count','overlap_count','source_pool_records','eligible_pool_records']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source_pickle')
    print(json.dumps(build(parser.parse_args().source_pickle),indent=2))
