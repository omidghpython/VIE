from __future__ import annotations
from dataclasses import dataclass
import importlib.metadata
import os
import platform
import random
import time


@dataclass
class Response:
    text: str
    prompt_tokens: int
    completion_tokens: int
    generation_seconds: float
    output_limit: bool = False


class HFBackend:
    """Local baseline Qwen identity; this adapter does not change baseline code/prompts."""
    def __init__(self, config):
        os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
        os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        started = time.perf_counter()
        self.torch = torch
        self.config = config
        if not torch.cuda.is_available():
            raise RuntimeError('This protocol requires CUDA and NF4; CPU substitution is not automatic.')
        kwargs = dict(revision=config['model_revision'], local_files_only=not config['allow_model_download'])
        self.tokenizer = AutoTokenizer.from_pretrained(config['model'], use_fast=True, **kwargs)
        self.model = AutoModelForCausalLM.from_pretrained(
            config['model'], **kwargs, device_map='auto', torch_dtype=torch.float16,
            low_cpu_mem_usage=True, quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16))
        self.model.eval()
        self.identity = dict(backend='transformers', model=config['model'], requested_revision=config['model_revision'],
                             loaded_revision=getattr(self.model.config, '_commit_hash', None),
                             quantization='NF4-double-quant', compute_dtype='float16', sampling=False,
                             python=platform.python_version(), cuda=torch.version.cuda,
                             gpu=torch.cuda.get_device_name(0),
                             packages={name: importlib.metadata.version(name) for name in
                                       ['torch', 'transformers', 'accelerate', 'bitsandbytes']})
        if self.identity['loaded_revision'] not in {None, config['model_revision']}:
            raise ValueError('Loaded model revision does not match requested baseline')
        self.load_seconds = time.perf_counter() - started

    def encode(self, messages):
        rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return self.tokenizer(rendered, return_tensors='pt', truncation=False)

    def count_tokens(self, messages):
        return int(self.encode(messages)['input_ids'].shape[1])

    def check_context(self, prompt_tokens, output_tokens):
        limit = getattr(self.model.config, 'max_position_embeddings', None)
        if isinstance(limit, int) and prompt_tokens + output_tokens > limit:
            raise ValueError('Input plus reserved output exceeds model context; nothing was truncated.')

    def generate(self, messages, max_new_tokens, seed):
        torch = self.torch
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        encoded = self.encode(messages)
        length = int(encoded['input_ids'].shape[1])
        self.check_context(length, max_new_tokens)
        device = self.model.get_input_embeddings().weight.device
        encoded = {key: value.to(device) for key, value in encoded.items()}
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            outputs = self.model.generate(**encoded, do_sample=False, max_new_tokens=max_new_tokens,
                                          use_cache=True, eos_token_id=self.tokenizer.eos_token_id,
                                          pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        new_ids = outputs[0, length:]
        eos = self.tokenizer.eos_token_id
        eos_ids = set(eos if isinstance(eos, list) else [eos])
        hit_limit = len(new_ids) >= max_new_tokens and (not len(new_ids) or int(new_ids[-1]) not in eos_ids)
        return Response(self.tokenizer.decode(new_ids, skip_special_tokens=True).strip(),
                        length, len(new_ids), elapsed, hit_limit)
