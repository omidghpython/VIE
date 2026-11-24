import csv
import json
from pathlib import Path
import zipfile
from .common import atomic_json, read_json
from .evaluation import load_trials
from .runner import summarize_run


def export_report(output):
    output=Path(output)
    if (output/'.run.lock').exists():
        raise RuntimeError('Wait until the running session releases the output lock.')
    summary=summarize_run(output)
    atomic_json(output/'summary.json',summary)
    fields=['case_id','source_question_id','arm','status','action','target_task_ids','query','answer',
            'llm_calls','prompt_tokens','completion_tokens','total_tokens','generation_seconds',
            'elapsed_seconds','retrieval_calls','error']
    with (output/'decisions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in load_trials(output):
            decision=(row.get('parsed') or {}).get('decision',{})
            flat={k:row.get(k) for k in ['case_id','source_question_id','arm','status','action','elapsed_seconds','error']}
            flat.update({k:row['usage'][k] for k in ['llm_calls','prompt_tokens','completion_tokens','total_tokens','generation_seconds','retrieval_calls']})
            flat.update({k:decision.get(k) for k in ['query','answer']})
            flat['target_task_ids']=json.dumps(decision.get('target_task_ids',[]),ensure_ascii=False)
            writer.writerow(flat)
    text=['# گزارش اجرای آزمایش تصمیم‌گیری شواهد','',
          'این آزمایش یک‌مرحله‌ای است. query پیشنهادی اجرا نشده و نتیجهٔ RAG کامل نیست.',
          'وضعیت‌های supported و stop قضاوت مدل‌اند؛ صحت معنایی به ارزیابی مستقل نیاز دارد.',
          f"نقش داده: {summary['role']}؛ رکوردهای ثبت‌شده: {summary['recorded_trials']} از {summary['expected_trials']}.",
          f"تکمیل اجرای برنامه: {summary['execution_complete']}؛ backend: {summary['backend'].get('backend')}.",
          '', '| حالت | فراخوانی مدل | توکن معلوم | توکن کل | فراخوانی با هزینه نامعلوم | بازیابی واقعی |',
          '|---|---:|---:|---:|---:|---:|']
    for arm,cost in summary['arms'].items():
        total=cost['total_tokens'] if cost['total_tokens'] is not None else 'نامعلوم؛ صفر نیست'
        text.append(f"| {arm} | {cost['llm_calls']} | {cost['known_total_tokens']} | {total} | {cost['unknown_usage_trials']} | ۰ |")
        text.extend(['',f"وضعیت‌های {arm}: `{json.dumps(cost['statuses'],ensure_ascii=False)}`",''])
    text.extend(['هزینهٔ تاریخی تولید درخت در این جدول نیست. هزینهٔ مدل تصمیم‌گیر، خطاها و خروجی ناقص حفظ شده‌اند.',
                 'تفاوت هزینهٔ ورودی دو حالت گزارش می‌شود؛ سقف یکسان است و ورودی برای هم‌اندازه‌کردن مصنوعی پر نمی‌شود.',
                 'شواهد اولیهٔ هر جفت یکسان‌اند؛ پوشش مرجع در این مرحله اثر بازیابی جدید نیست.',
                 'فایل decisions.csv برای مرور تصمیم‌ها؛ trials برای متن دقیق پیام‌ها، پاسخ خام، هزینه و مشاهده‌گر ساختاری است.'])
    if (output/'evaluation.json').exists():
        text.extend(['','ارزیابی مستقل در evaluation.json موجود است؛ مخرج‌ها و میزان تکمیل داوری را همراه درصدها بخوانید.'])
    else:
        text.extend(['','ارزیابی مستقل هنوز وارد نشده است؛ دقت تصمیم و اعتبار ارجاع گزارش نمی‌شود.'])
    (output/'report_FA.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return {'csv':str(output/'decisions.csv'),'report':str(output/'report_FA.md')}


def bundle_results(output, destination):
    output,destination=Path(output),Path(destination)
    export_report(output)
    if destination.exists():
        raise ValueError('Bundle already exists; choose a new filename')
    files=[output/name for name in ['manifest.json','runtime_cases.json','summary.json','decisions.csv','report_FA.md']]
    files+=sorted((output/'trials').glob('*.json'))
    if (output/'evaluation.json').exists():files.append(output/'evaluation.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,arcname='evidence_planning_results/'+str(path.relative_to(output)))
    return {'bundle':str(destination),'files':len(files)}
