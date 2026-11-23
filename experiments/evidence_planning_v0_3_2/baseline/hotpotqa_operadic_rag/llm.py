"""Local Qwen with explicit budgets and no silent input/JSON truncation."""
import json
import logging
from .config import (MODEL_NAME, MODEL_REVISION, DEFAULT_MAX_INPUT_TOKENS, DEFAULT_MAX_NEW_TOKENS,
                     DEFAULT_INTERMEDIATE_TOKENS, DEFAULT_PLAN_TOKENS)
from .contracts import parse_json_object
from .retriever import format_evidence
from .telemetry import install_generate_wrapper

LOGGER = logging.getLogger('hotpotqa_operadic_rag')
SYSTEM_ANSWER = ('Use only the supplied evidence. Return a factual answer of at most five words, '
                 'or an empty response if the answer is unsupported. No reasoning or commentary.')


class InputBudgetError(RuntimeError):
    pass


class OutputBudgetError(RuntimeError):
    pass


def require_short_answer(answer):
    if not isinstance(answer, str):
        raise ValueError('Answer must be text.')
    answer = answer.strip()
    if len(answer.split()) > 5:
        raise ValueError('Final answer exceeds five whitespace-delimited words; not silently truncated.')
    return answer


class LocalQwen:
    def __init__(self, use_4bit=True, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS,
                 max_new_tokens=DEFAULT_MAX_NEW_TOKENS,
                 intermediate_tokens=DEFAULT_INTERMEDIATE_TOKENS, plan_tokens=DEFAULT_PLAN_TOKENS):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        for value in (max_input_tokens, max_new_tokens, intermediate_tokens, plan_tokens):
            if type(value) is not int or value <= 0:
                raise ValueError('Token budgets must be positive integers.')
        self.max_input_tokens, self.max_new_tokens = max_input_tokens, max_new_tokens
        self.intermediate_tokens, self.plan_tokens = intermediate_tokens, plan_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION, use_fast=True)
        kwargs = {'torch_dtype': 'auto', 'device_map': 'auto', 'low_cpu_mem_usage': True}
        if use_4bit:
            if not torch.cuda.is_available():
                raise RuntimeError('4-bit loading requires CUDA; CPU needs --allow-cpu --no-4bit.')
            kwargs['quantization_config'] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, revision=MODEL_REVISION, **kwargs)
        self.model.eval()
        self.model.config.use_cache = True
        install_generate_wrapper(self.model)
        LOGGER.info('Qwen device: %s', self.model.get_input_embeddings().weight.device)

    def generate(self, messages, max_new_tokens=None):
        import torch
        budget = self.max_new_tokens if max_new_tokens is None else int(max_new_tokens)
        rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        encoded = self.tokenizer(rendered, return_tensors='pt', truncation=False)
        input_len = int(encoded['input_ids'].shape[1])
        if input_len > self.max_input_tokens:
            raise InputBudgetError(f'Input has {input_len} tokens; limit is {self.max_input_tokens}. '
                                   'No evidence or question text was silently discarded.')
        context_limit = getattr(self.model.config, 'max_position_embeddings', None)
        if isinstance(context_limit, int) and input_len + budget > context_limit:
            raise InputBudgetError('Input plus reserved output exceeds the model context limit.')
        device = self.model.get_input_embeddings().weight.device
        encoded = {key: value.to(device) for key, value in encoded.items()}
        eos = self.tokenizer.eos_token_id
        with torch.inference_mode():
            output = self.model.generate(**encoded, do_sample=False, max_new_tokens=budget,
                                         use_cache=True, eos_token_id=eos,
                                         pad_token_id=self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else eos)
        new_ids = output[0, input_len:]
        end_ids = set(eos if isinstance(eos, list) else [eos])
        if len(new_ids) >= budget and (not len(new_ids) or int(new_ids[-1]) not in end_ids):
            raise OutputBudgetError(f'Output reached the {budget}-token limit without EOS; incomplete output rejected.')
        return self.tokenizer.decode(new_ids, skip_special_tokens=True).strip()

    def ask_json(self, user_prompt):
        raw = self.generate([
            {'role': 'system', 'content': 'Return exactly the requested JSON object. No prose or invented evidence.'},
            {'role': 'user', 'content': user_prompt}], max_new_tokens=self.intermediate_tokens)
        # No default object is substituted when the output is malformed.
        return parse_json_object(raw)

    def answer(self, question, evidence, trace=None):
        prompt = f'Question:\n{question}\n\nEvidence:\n{format_evidence(evidence)}'
        if trace is not None:
            prompt += '\n\nSupported bindings:\n' + json.dumps(trace, ensure_ascii=False, separators=(',', ':'))
        return require_short_answer(self.generate([
            {'role': 'system', 'content': SYSTEM_ANSWER}, {'role': 'user', 'content': prompt}]))

    def shorten_answer(self, question, evidence, bindings, final):
        prompt = ('Original question:\n' + question + '\nRoot ID: ' + final + '\nBindings:\n' +
                  json.dumps(bindings, ensure_ascii=False, separators=(',', ':')) +
                  '\nEvidence:\n' + format_evidence(evidence))
        return require_short_answer(self.generate([
            {'role': 'system', 'content': 'Shorten the supplied root answer to at most five words. '
             'Preserve its entity, value, negation and requested type. Do not solve the question anew. '
             'Return only the shortened answer, or empty if it cannot faithfully fit.'},
            {'role': 'user', 'content': prompt}]))
