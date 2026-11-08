"""Replay saved outputs with the delivered code; no model calls or source edits.

Usage: python verify_run.py SOURCE RUN_ROOT BASELINE_ROOT OUTPUT_JSON
"""
from pathlib import Path
import sys, json, hashlib, copy, tempfile, shutil, zipfile, collections, io
sys.dont_write_bytecode = True
source, root, baseline, output = map(Path, sys.argv[1:5])
sys.path.insert(0, str(source))
import decomposition_pilot as pilot
from hotpotqa_operadic_rag import decomposition as d
from hotpotqa_operadic_rag.contracts import parse_json_object, validate_plan
from hotpotqa_operadic_rag.checkpoint import RunStore, digest
from hotpotqa_operadic_rag.max4_comparison import reference_digest

read = lambda p: json.loads(p.read_text(encoding='utf-8'))
manifest = read(root/'trees.csv.state/manifest.json')
base_manifest = read(baseline/'trees.csv.state/manifest.json')
settings = manifest['settings']
samples, baselines = pilot.load_cohort(source/'evaluation/samples.json')
assert samples == read(root/'trees.csv.state/samples.json') == read(baseline/'trees.csv.state/samples.json')
assert digest(samples) == manifest['samples_sha256'] == settings['sample_snapshot_sha256']
delivered_digest = pilot.code_digest()
assert delivered_digest == read(source/'VERIFICATION.json')['source_code_sha256']
source_matches = delivered_digest == settings['code_sha256']
assert digest(baselines) == settings['baselines_sha256']
assert digest(pilot.direct_reference()) == settings['direct_reference_sha256']
assert reference_digest() == settings['max4_reference_sha256']
assert hashlib.sha256(d.PLAN_SYSTEM.encode()).hexdigest() == settings['plan_prompt_sha256']
assert hashlib.sha256(d.REVIEW_SYSTEM.encode()).hexdigest() == settings['review_prompt_sha256']
assert manifest['runtime_identity'] == base_manifest['runtime_identity']
differences = {k:dict(baseline=base_manifest['settings'].get(k),current=settings.get(k))
               for k in set(settings)|set(base_manifest['settings']) if settings.get(k)!=base_manifest['settings'].get(k)}
assert set(differences) <= {'code_sha256','max4_reference_sha256','target_patch_mode','target_patch_max_calls'}
repair = settings.get('target_patch_mode') == 'root_patch'

class Replay:
    plan_tokens = 3072
    last_raw_output = None
    def __init__(self, raw): self.raw, self.messages, self.prompts = list(raw), [], []
    def generate(self, messages, **kwargs):
        self.messages.append(copy.deepcopy(messages))
        self.last_raw_output = self.raw.pop(0)
        return self.last_raw_output
    def ask_json(self, prompt):
        self.prompts.append(prompt)
        self.last_raw_output = self.raw.pop(0)
        return parse_json_object(self.last_raw_output)

counts = collections.Counter()
rows = []
for order, sample in enumerate(samples, 1):
    qid = sample['question_id']
    record = read(root/'trees.csv.state/questions'/(qid+'.json'))
    old = read(baseline/'trees.csv.state/questions'/(qid+'.json'))
    assert record['question_id'] == qid
    structure = record['phases']['structure']
    trace = structure['result']['decomposition_trace']
    fake = Replay([e['raw_output'] for e in trace])
    try:
        result = pilot.generate_result(fake, sample['question'], **({'target_repair':True} if repair else {}))
        status, error = 'valid', ''
    except d.DecompositionError as exc:
        result, status, error = exc.details, 'invalid', str(exc)
    assert (status,error,result) == (structure['status'],structure['error'],structure['result']), (order,'structure replay')
    assert not fake.raw and len(fake.messages)==len(trace)<=2
    assert fake.messages[0][1]['content'] == sample['question']
    counts['generation_calls'] += len(trace)
    counts['original_structure_calls'] += sum(e['stage']=='structure' for e in trace)
    counts['target_patch_calls'] += sum(e['stage']=='target_root_patch' for e in trace)
    counts['raw_first_attempt_structurally_valid'] += trace[0]['status']=='valid'
    counts['final_structure_valid'] += status=='valid'
    review = record['phases'].get('review')
    if review:
        fake_review = Replay([review['result']['raw_output']] if review['result']['raw_output'] is not None else [])
        assert pilot.review_result(fake_review,sample['question'],result['plan']) == review['result'], (order,'review replay')
        assert not fake_review.raw
        counts['review_decisions'] += 1
        counts['judge_calls'] += bool(fake_review.prompts)
    else:
        assert status == 'invalid'
    for phase_name, phase in record['phases'].items():
        assert len(phase['history'])==1, (order,'unexpected previous attempts')
        assert phase['history'][0] == {k:phase[k] for k in ('status','error','telemetry')}
        t = phase['telemetry']
        assert t['prompt_tokens']+t['completion_tokens']==t['total_tokens']
        assert t['retrieval_steps']==0
        expected_calls = len(trace) if phase_name=='structure' else int(review['result']['raw_output'] is not None)
        assert t['llm_calls']==expected_calls, (order,phase_name,'telemetry calls')
        counts['histories_checked'] += 1
    old_st = old['phases']['structure']
    old_trace = old_st['result']['decomposition_trace']
    current_structure_trace = [e for e in trace if e['stage']=='structure']
    old_review = old['phases'].get('review',{}).get('result')
    new_review = (review or {}).get('result')
    def cost(rec):
        return {key:sum(h['telemetry'].get(key,0) for ph in rec['phases'].values() for h in ph['history'])
                for key in ('llm_calls','prompt_tokens','completion_tokens','total_tokens','execution_time_sec')}
    rows.append(dict(order=order,question_id=qid,question=sample['question'],
        status_before=old_st['status'],status_after=status,
        plan_equal=result.get('plan')==old_st['result'].get('plan'),
        structure_raw_equal=[e['raw_output'] for e in current_structure_trace]==[e['raw_output'] for e in old_trace],
        first_raw_equal=trace[0]['raw_output']==old_trace[0]['raw_output'],
        full_structure_result_equal=result==old_st['result'],review_equal=new_review==old_review,
        judge_raw_equal=(new_review or {}).get('raw_output')==(old_review or {}).get('raw_output'),
        cost_before=cost(old),cost_after=cost(record),
        target_patch=result.get('target_patch'), plan_before=old_st['result'].get('plan'),plan_after=result.get('plan')))

summary = read(root/'summary.json')
assert counts['generation_calls']+counts['judge_calls']==summary['total_cost']['llm_calls']
assert summary['requested']==40 and summary['incomplete_questions']==summary['backend_errors']==0
reports = ['summary.json','trees.csv','review.md','max4_comparison.json','max4_comparison.md']
if (root/'diagnostics.json').exists(): reports += ['diagnostics.json','diagnostics.md']
with tempfile.TemporaryDirectory() as tmp:
    dest = Path(tmp)/root.name
    shutil.copytree(root/'trees.csv.state',dest/'trees.csv.state')
    store = RunStore(dest/'trees.csv',settings,lambda:samples)
    regenerated = pilot.export_reports(store,baselines)
    assert regenerated==summary, 'summary regeneration'
    for name in reports:
        if name.endswith('.json'): assert read(dest/name)==read(root/name), name
        else: assert (dest/name).read_text(encoding='utf-8-sig')==(root/name).read_text(encoding='utf-8-sig'),name
    archive = dest.with_name(dest.name+'_results.zip')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        report_members=len(z.namelist())
    # Same source and settings + complete checkpoint: run_pilot must not instantiate a model.
    from unittest.mock import patch
    with patch.object(pilot,'create_model',side_effect=AssertionError('Unexpected live model load')):
        if source_matches:
            resumed = pilot.run_pilot(samples,baselines,dest,**({'target_repair':True} if repair else {}))
            assert resumed==summary
        else:
            try:
                pilot.run_pilot(samples,baselines,dest,**({'target_repair':True} if repair else {}))
            except ValueError as exc:
                assert 'settings/code differ' in str(exc)
            else:
                raise AssertionError('Mismatched source identity was not blocked on resume')

result = dict(experiment=source.name.removeprefix('hotpotqa_'),received_settings=settings,
    runtime_identity=manifest['runtime_identity'],settings_differences_vs_original=differences,
    source_identity_verified=source_matches,delivered_code_sha256=delivered_digest,
    recorded_code_sha256=settings['code_sha256'],same_samples=True,runtime_identity_same_as_baseline=True,
    verification_counts=dict(counts),all_raw_outputs_replayed_exactly=True,reports_regenerated=reports,
    report_archive_members=report_members,complete_resume_without_model_verified=source_matches,
    mismatched_source_resume_correctly_blocked=not source_matches,
    invalid_orders=[r['order'] for r in rows if r['status_after']=='invalid'],
    final_plan_changed_orders=[r['order'] for r in rows if not r['plan_equal']],
    raw_structure_changed_orders=[r['order'] for r in rows if not r['structure_raw_equal']],
    first_raw_changed_orders=[r['order'] for r in rows if not r['first_raw_equal']],
    review_changed_orders=[r['order'] for r in rows if not r['review_equal']],
    raw_judge_changed_orders=[r['order'] for r in rows if not r['judge_raw_equal']],
    summary=summary,per_question=rows,
    diagnostics=read(root/'diagnostics.json') if (root/'diagnostics.json').exists() else None,
    live_model_calls_during_analysis=0,
    limits=['Identity is checked against recorded manifests and delivered source, not independent observation of GPU execution.',
            'Token totals checked against telemetry; original tokenizer token IDs are not in these artifacts.',
            'No answer accuracy or independent semantic benchmark measured.'])
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(experiment=result['experiment'],verification=dict(counts),invalid=result['invalid_orders'],
                     changed_plans=result['final_plan_changed_orders'],changed_raw=result['raw_structure_changed_orders'],
                     changed_judge=result['raw_judge_changed_orders'],reports_verified=len(reports)),ensure_ascii=False))
