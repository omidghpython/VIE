"""Shared utilities: logging, runtime checks, parsing and deterministic seeds."""
import logging
import random
import re
import json
import sys
from typing import Any, Dict, Optional, Sequence

import numpy as np

from .config import RANDOM_SEED

LOGGER = logging.getLogger("hotpotqa_operadic_rag")

def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

def set_seed(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def cuda_sync() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.synchronize()

def check_runtime(require_cuda: bool = True) -> None:
    """Fail early with useful diagnostics if the VM cannot see the GPU."""
    import torch
    LOGGER.info("Python: %s", sys.version.replace("\n", " "))
    LOGGER.info("PyTorch: %s", torch.__version__)
    LOGGER.info("PyTorch CUDA build: %s", torch.version.cuda)
    LOGGER.info("CUDA available: %s", torch.cuda.is_available())

    if not torch.cuda.is_available():
        message = (
            "PyTorch cannot access an NVIDIA CUDA GPU. In the Windows VM, "
            "verify PCI passthrough, install the NVIDIA Windows driver, and "
            "confirm that `nvidia-smi` works. Then install a CUDA-enabled "
            "PyTorch build in this same Python environment."
        )
        if require_cuda:
            raise RuntimeError(message)
        LOGGER.warning(message)
        return

    for gpu_index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(gpu_index)
        total_gib = props.total_memory / (1024 ** 3)
        LOGGER.info(
            "GPU %d: %s | compute capability %s | VRAM %.2f GiB",
            gpu_index,
            props.name,
            f"{props.major}.{props.minor}",
            total_gib,
        )

    if "3080 Ti" not in torch.cuda.get_device_name(0):
        LOGGER.warning(
            "The visible GPU is not named RTX 3080 Ti. The script will still "
            "run if the GPU has sufficient CUDA support and memory."
        )

def safe_minmax(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return arr
    lo, hi = float(np.min(arr)), float(np.max(arr))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo <= 1e-12:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)

def parse_json_object(
    raw_text: str,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse a JSON object, including one embedded in Markdown or prose."""
    result = dict(defaults or {})
    if not isinstance(raw_text, str) or not raw_text.strip():
        return result

    text = raw_text.strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)

    candidates = [text]
    for start, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for end in range(start, len(text)):
            current = text[end]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:end + 1])
                    break

    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                merged = dict(result)
                merged.update(obj)
                return merged
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return result

def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "sufficient"}:
            return True
        if normalized in {"false", "no", "0", "insufficient"}:
            return False
    return default

def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()

def clear_cuda_cache() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
