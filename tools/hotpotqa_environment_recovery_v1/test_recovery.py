"""Software checks only. No package installation, model download or GPU work."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import restore_environment as recovery


def project_fixture(root):
    texts={
        'requirements-live.txt':'torch>=2.4,<3\n',
        'requirements-test.txt':'numpy>=1.26\n',
        'run.py':'# synthetic fixture; never invoked\n',
        'run_rag.py':'# synthetic fixture; never invoked\n',
        'configs/rag_development.json':json.dumps(dict(model=recovery.QWEN[0],model_revision=recovery.QWEN[1],allow_model_download=False)),
        'data/final15_usage.json':'{"status":"already_used_synthetic_marker"}',
    }
    for name,text in texts.items():
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
    manifest=dict(version='0.3.0',files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in texts})
    (root/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest))
    return root


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.project=Path(self.temp.name)/'project with spaces'
        self.project.mkdir()
        project_fixture(self.project)
    def tearDown(self):self.temp.cleanup()

    def test_plan_does_not_install_create_environment_or_change_files(self):
        before={p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        with patch.object(recovery.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(recovery.main(['--project',str(self.project),'--plan']),0)
        run.assert_not_called()
        self.assertEqual(before,{p.relative_to(self.project):p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

    def test_cuda_torch_installed_first_and_every_pip_uses_same_environment(self):
        commands=recovery.command_plan(self.project,platform='nt')
        expected=str(self.project/'.venv_hotpotqa/Scripts/python.exe')
        self.assertTrue(all(c[0]==expected for c in commands))
        self.assertIn(recovery.TORCH_SPEC,commands[1])
        self.assertIn(recovery.TORCH_INDEX,commands[1])
        self.assertIn(str(self.project/'requirements-live.txt'),commands[2])
        self.assertTrue(commands[4][-1]=='--gpu-probe' and commands[5][-1]=='--prepare-models')

    def test_plan_never_starts_development_or_final_evaluation(self):
        commands=recovery.command_plan(self.project)
        program_commands=[c for c in commands if Path(c[1]).name in {'run.py','run_rag.py'}]
        self.assertEqual(len(program_commands),2)
        self.assertTrue(all(c[2:]==['verify'] for c in program_commands))
        self.assertFalse(any('run-final15' in c for c in commands))

    def test_changed_project_is_rejected_without_overwriting_it(self):
        p=self.project/'run_rag.py'
        p.write_text('user local change')
        with self.assertRaises(ValueError):recovery.validate_project(self.project)
        self.assertEqual(p.read_text(),'user local change')

    def test_missing_driver_stops_before_environment_and_download(self):
        with patch.object(recovery.shutil,'which',return_value=None),patch.object(recovery,'execute') as execute:
            with self.assertRaises(RuntimeError):recovery.restore(self.project)
        execute.assert_not_called()
        self.assertFalse((self.project/'.venv_hotpotqa').exists())

    def test_incomplete_existing_environment_is_preserved(self):
        env=self.project/'.venv_hotpotqa'
        env.mkdir()
        sentinel=env/'keep.txt'
        sentinel.write_text('existing data')
        with patch.object(recovery.shutil,'which',return_value='nvidia-smi'),patch.object(recovery,'execute') as execute:
            with self.assertRaises(RuntimeError):recovery.restore(self.project)
        self.assertEqual(execute.call_count,1)
        self.assertEqual(sentinel.read_text(),'existing data')

    def test_gpu_check_failure_prevents_large_model_download(self):
        def command(cmd,project):
            if '--gpu-probe' in cmd:raise subprocess.CalledProcessError(1,cmd)
        with patch.object(recovery.shutil,'which',return_value='nvidia-smi'),patch.object(recovery,'execute',side_effect=command) as execute:
            with self.assertRaises(subprocess.CalledProcessError):recovery.restore(self.project)
        self.assertFalse(any('--prepare-models' in call.args[0] for call in execute.call_args_list))
        report=json.loads(next((self.project/'recovery_logs').glob('*.json')).read_text())
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['current_step'],5)

    def test_nonisolated_python_refuses_pip_install(self):
        def command(cmd,project):
            if '-c' in cmd:raise subprocess.CalledProcessError(1,cmd)
        with patch.object(recovery.shutil,'which',return_value='nvidia-smi'),patch.object(recovery,'execute',side_effect=command) as execute:
            with self.assertRaises(subprocess.CalledProcessError):recovery.restore(self.project)
        self.assertFalse(any('pip' in call.args[0] for call in execute.call_args_list))

    def test_success_preserves_config_and_final_usage_marker(self):
        config=(self.project/'configs/rag_development.json').read_bytes()
        marker=(self.project/'data/final15_usage.json').read_bytes()
        with patch.object(recovery.shutil,'which',return_value='nvidia-smi'),patch.object(recovery,'execute'):
            recovery.restore(self.project)
        self.assertEqual((self.project/'configs/rag_development.json').read_bytes(),config)
        self.assertEqual((self.project/'data/final15_usage.json').read_bytes(),marker)
        report=json.loads(next((self.project/'recovery_logs').glob('*.json')).read_text())
        self.assertEqual(report['status'],'ready')
        self.assertEqual(report['project_questions_executed'],0)

    def test_qwen_missing_shard_is_not_reported_ready(self):
        snapshot=Path(self.temp.name)/'snapshot'
        snapshot.mkdir()
        for name in ['config.json','tokenizer_config.json','tokenizer.json','generation_config.json']:
            (snapshot/name).write_text('{}')
        (snapshot/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'weight':'model-00001-of-00001.safetensors'}}))
        with self.assertRaises(RuntimeError):recovery.verify_weight_files(snapshot,'qwen')
        (snapshot/'model-00001-of-00001.safetensors').write_bytes(b'synthetic test only')
        recovery.verify_weight_files(snapshot,'qwen')

    def test_bge_missing_weights_is_not_reported_ready(self):
        snapshot=Path(self.temp.name)/'bge'
        snapshot.mkdir()
        for name in ['config.json','tokenizer_config.json','vocab.txt']:(snapshot/name).write_text('test')
        with self.assertRaises(RuntimeError):recovery.verify_weight_files(snapshot,'bge')
        (snapshot/'model.safetensors').write_bytes(b'synthetic test only')
        recovery.verify_weight_files(snapshot,'bge')


if __name__=='__main__':unittest.main()
