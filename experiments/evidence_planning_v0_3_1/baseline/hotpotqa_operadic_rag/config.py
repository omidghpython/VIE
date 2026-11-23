"""Central configuration for Windows VM / RTX 3080 Ti execution."""
import os

# Set environment before importing torch/transformers in entry points.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
# Exact revisions recorded in the user's baseline run; existing cache is reused.
MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
EMBEDDING_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
DATASET_NAME = "hotpot_qa"
DATASET_CONFIG = "distractor"
DATASET_SPLIT = "validation"

DEFAULT_N_SAMPLES = 40
MAX_RETRIEVALS = 2
TOP_K = 3
HYBRID_ALPHA = 0.6
DEFAULT_MAX_NEW_TOKENS = 150
DEFAULT_MAX_INPUT_TOKENS = 8500
RANDOM_SEED = 42
DEFAULT_OUTPUT = "results/hotpotqa_qwen25_operadic_rag_results_v3_2_4_max4.csv"
DEFAULT_USE_4BIT = True
DEFAULT_EMBEDDING_DEVICE = "cuda"

DEFAULT_INTERMEDIATE_TOKENS = 512
DEFAULT_PLAN_TOKENS = 3072
MAX_PLAN_NODES = 4
PLAN_ATTEMPTS = 2
RUN_SCHEMA_VERSION = 4
