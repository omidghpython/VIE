"""Command-line interface."""
import argparse
import os

from .config import (
    DEFAULT_MAX_INPUT_TOKENS, DEFAULT_MAX_NEW_TOKENS, DEFAULT_N_SAMPLES,
    DEFAULT_OUTPUT, DEFAULT_USE_4BIT, DEFAULT_INTERMEDIATE_TOKENS, DEFAULT_PLAN_TOKENS,
)
from .experiment import run_experiment

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Standard RAG and Operadic-Guided RAG on HotpotQA."
    )
    parser.add_argument("--n-samples", type=int, default=int(os.getenv("N_SAMPLES", DEFAULT_N_SAMPLES)))
    parser.add_argument(
        "--use-4bit", dest="use_4bit", action="store_true",
        help="Use NF4 4-bit model quantization (recommended for RTX 3080 Ti 12GB).",
    )
    parser.add_argument(
        "--no-4bit", dest="use_4bit", action="store_false",
        help="Load full precision/auto dtype model; not recommended for 12GB VRAM.",
    )
    parser.set_defaults(use_4bit=os.getenv("USE_4BIT", "1").lower() not in {"0", "false", "no"})
    parser.add_argument("--max-input-tokens", type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument("--intermediate-tokens", type=int, default=DEFAULT_INTERMEDIATE_TOKENS)
    parser.add_argument("--plan-tokens", type=int, default=DEFAULT_PLAN_TOKENS)
    parser.add_argument("--output-csv", default=os.getenv("OUTPUT_CSV", DEFAULT_OUTPUT))
    parser.add_argument("--samples-json", default=None,
                        help="Reuse exact saved samples/order/contexts (e.g. evaluation/samples.json).")
    parser.add_argument(
        "--allow-cpu", action="store_true",
        help="Allow CPU-only execution if CUDA is unavailable (very slow).",
    )
    return parser

def main() -> None:
    args = build_arg_parser().parse_args()
    try:
        result = run_experiment(
            n_samples=args.n_samples,
            use_4bit=args.use_4bit,
            max_input_tokens=args.max_input_tokens,
            max_new_tokens=args.max_new_tokens,
            output_csv=args.output_csv,
            require_cuda=not args.allow_cpu,
            intermediate_tokens=args.intermediate_tokens,
            plan_tokens=args.plan_tokens,
            samples_json=args.samples_json,
        )
    except KeyboardInterrupt:
        print("Interrupted; completed phases are saved. Rerun with the same settings to resume.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"Experiment blocked: {type(exc).__name__}: {exc}")
        raise SystemExit(2)
    raise SystemExit(0 if result.attrs.get("run_complete") else 2)
