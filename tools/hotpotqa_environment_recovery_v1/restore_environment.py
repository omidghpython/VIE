"""Rebuild the v0.3 environment and cache; never run an evaluation or edit its config."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone

TORCH_SPEC = 'torch==2.11.0+cu128'
TORCH_INDEX = 'https://download.pytorch.org/whl/cu128'
QWEN = ('Qwen/Qwen2.5-7B-Instruct', 'a09a35458c702b33eeacc393d103063234e8bc28')
BGE = ('BAAI/bge-small-en-v1.5', '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a')
QWEN_FILES = ['config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json',
              'vocab.json', 'merges.txt', 'model.safetensors.index.json', 'model-*.safetensors', 'model.safetensors']
BGE_FILES = ['*.json', '*.txt', '*.safetensors', 'pytorch_model.bin']
HERE = Path(__file__).resolve().parent


def validate_project(project):
    project = Path(project).resolve()
    for name in ['PACKAGE_MANIFEST.json', 'requirements-live.txt', 'requirements-test.txt', 'run.py', 'run_rag.py']:
        if not (project/name).is_file():
            raise ValueError('Extract the COMPLETE recovery ZIP first; missing project file: '+name)
    manifest = json.loads((project/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['version'] != '0.3.0':
        raise ValueError('This recovery kit targets evidence-planning 0.3.0.')
    for name, expected in manifest['files'].items():
        path = (project/name).resolve()
        if not path.is_relative_to(project) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Project file missing or changed; it was NOT overwritten: '+name)
    config = json.loads((project/'configs/rag_development.json').read_text(encoding='utf-8'))
    if (config['model'], config['model_revision']) != QWEN:
        raise ValueError('Unexpected model identity; do not download a substitute.')
    return project


def check_python():
    if not (3, 10) <= sys.version_info[:2] <= (3, 13) or struct.calcsize('P') != 8:
        raise RuntimeError('Use standard 64-bit Python 3.10–3.13 (Python 3.13 preferred for the previous Windows setup).')


def venv_python(project, platform=None):
    base = Path(project)/'.venv_hotpotqa'
    return base/('Scripts/python.exe' if (platform or os.name) == 'nt' else 'bin/python')


def command_plan(project, platform=None):
    python = str(venv_python(project, platform))
    return [
        [python, '-m', 'pip', 'install', '--upgrade', 'pip'],
        [python, '-m', 'pip', 'install', '--index-url', TORCH_INDEX, TORCH_SPEC],
        [python, '-m', 'pip', 'install', '-r', str(project/'requirements-live.txt'),
         '-r', str(project/'requirements-test.txt'), '-c', str(HERE/'recovery_constraints.txt')],
        [python, '-m', 'pip', 'check'],
        [python, str(HERE/'restore_environment.py'), '--project', str(project), '--gpu-probe'],
        [python, str(HERE/'restore_environment.py'), '--project', str(project), '--prepare-models'],
        [python, str(project/'run.py'), 'verify'],
        [python, str(project/'run_rag.py'), 'verify'],
    ]


def gpu_probe():
    import torch
    import bitsandbytes as bnb
    if str(torch.__version__) != '2.11.0+cu128' or torch.version.cuda != '12.8':
        raise RuntimeError('Expected the pinned CUDA PyTorch build, not a CPU or different build.')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is not visible. Restore/update the NVIDIA driver or GPU passthrough through the cloud provider.')
    # Tiny synthetic kernel check; no Qwen loading and no project questions.
    layer = bnb.nn.Linear4bit(64, 64, bias=False, compute_dtype=torch.float16,
                             compress_statistics=True, quant_type='nf4').to('cuda')
    with torch.inference_mode():
        value = layer(torch.ones(1, 64, dtype=torch.float16, device='cuda'))
    torch.cuda.synchronize()
    if not bool(torch.isfinite(value).all()):
        raise RuntimeError('NF4 CUDA check produced non-finite values.')
    print(json.dumps(dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                          gpu=torch.cuda.get_device_name(0), nf4_kernel_check='passed',
                          project_question_inference=False), indent=2))


def verify_weight_files(snapshot, model_kind):
    snapshot = Path(snapshot)
    required = ['config.json', 'tokenizer_config.json']
    if model_kind == 'qwen':
        required += ['tokenizer.json', 'generation_config.json']
        index = snapshot/'model.safetensors.index.json'
        if index.exists():
            mapping = json.loads(index.read_text(encoding='utf-8')).get('weight_map', {})
            if not mapping:
                raise RuntimeError('Empty Qwen weight index')
            required += sorted(set(mapping.values()))
        else:
            required += ['model.safetensors']
    else:
        required += ['vocab.txt']
        if not any((snapshot/n).is_file() and (snapshot/n).stat().st_size for n in ['model.safetensors', 'pytorch_model.bin']):
            raise RuntimeError('BGE weights are missing from the snapshot')
    for name in required:
        path = snapshot/name
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError('Missing cached model file: '+name)


def prepare_models(verify_only=False):
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '120')
    os.environ.setdefault('HF_HUB_ETAG_TIMEOUT', '60')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoTokenizer
    from sentence_transformers import SentenceTransformer
    for model_kind, (repo, revision), patterns in [('qwen', QWEN, QWEN_FILES), ('bge', BGE, BGE_FILES)]:
        print('Preparing pinned model:', repo, revision, flush=True)
        path = snapshot_download(repo_id=repo, revision=revision, allow_patterns=patterns,
                                 local_files_only=verify_only)
        verify_weight_files(path, model_kind)
        AutoConfig.from_pretrained(repo, revision=revision, local_files_only=True)
        AutoTokenizer.from_pretrained(repo, revision=revision, local_files_only=True)
    # Check that the actual embedding loader can use the offline cache.
    # No encode() and no Qwen generation are called here.
    encoder = SentenceTransformer(BGE[0], revision=BGE[1], device='cpu', local_files_only=True)
    del encoder
    print('Qwen files/tokenizer and BGE offline loading verified. No evaluation was run.')


def execute(command, project):
    print('\nRunning:', subprocess.list2cmdline([str(x) for x in command]), flush=True)
    subprocess.run([str(x) for x in command], cwd=project, check=True)


def restore(project):
    check_python()
    project = validate_project(project)
    report = dict(started_utc=datetime.now(timezone.utc).isoformat(), status='running', completed_steps=[],
                  python=sys.version.split()[0], target_torch=TORCH_SPEC, model_revisions=dict(qwen=QWEN[1], bge=BGE[1]),
                  project_questions_executed=0, pipeline_files_modified=False)
    logs = project/'recovery_logs'
    logs.mkdir(exist_ok=True)
    report_path = logs/('restore-'+str(time.time_ns())+'.json')
    try:
        driver_tool = shutil.which('nvidia-smi')
        if not driver_tool:
            raise RuntimeError('nvidia-smi was not found. Install/restore the NVIDIA driver on the GPU machine first; pip does not install a driver.')
        execute([driver_tool, '-L'], project)
        python = venv_python(project)
        environment = project/'.venv_hotpotqa'
        if not python.exists():
            if environment.exists():
                raise RuntimeError('Incomplete .venv_hotpotqa directory; it was NOT deleted. Move it aside before retrying.')
            execute([sys.executable, '-m', 'venv', str(environment)], project)
        execute([str(python), '-c',
                 'import pathlib,sys; expected=pathlib.Path(sys.argv[1]).resolve(); '
                 'assert sys.prefix != sys.base_prefix and pathlib.Path(sys.prefix).resolve()==expected, '
                 '"Refusing to install packages outside the selected virtual environment"',
                 str(environment)], project)
        for index, command in enumerate(command_plan(project), 1):
            report['current_step'] = index
            report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            execute(command, project)
            report['completed_steps'].append(index)
        validate_project(project)
        report['status'] = 'ready'
        print('\nREADY. Use start_development_windows.bat to run with this environment.')
        print('No final15 or other research question was evaluated.')
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print('Recovery status:', report_path, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=HERE)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--plan', action='store_true', help='Print commands only: no installation, download, file creation or inference')
    group.add_argument('--gpu-probe', action='store_true')
    group.add_argument('--prepare-models', action='store_true')
    group.add_argument('--verify-models', action='store_true')
    args = parser.parse_args(argv)
    try:
        project = validate_project(args.project)
        if args.plan:
            print(json.dumps(dict(commands=command_plan(project), project_questions_executed=0,
                                  config_changes=False, models=[QWEN, BGE]), indent=2))
        elif args.gpu_probe:
            gpu_probe()
        elif args.prepare_models or args.verify_models:
            prepare_models(verify_only=args.verify_models)
        else:
            restore(project)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print('\nRESTORE FAILED:', f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
