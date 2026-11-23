"""Per-question/per-method generation and retrieval telemetry."""
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


from .config import MAX_RETRIEVALS
from .utils import cuda_sync

_ACTIVE_TRACKER = None

class TelemetryTracker:
    def __init__(self, name: str):
        self.name = name
        self.reset()

    def reset(self) -> None:
        self.retrieval_steps = 0
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.execution_time_sec = 0.0
        self._started_at: Optional[float] = None

    def start(self) -> None:
        self.reset()
        cuda_sync()
        self._started_at = time.perf_counter()

    def stop(self) -> None:
        cuda_sync()
        if self._started_at is not None:
            self.execution_time_sec = time.perf_counter() - self._started_at
            self._started_at = None

    def add_retrieval(self) -> None:
        if self.retrieval_steps >= MAX_RETRIEVALS:
            raise RuntimeError(
                f"{self.name}: retrieval limit ({MAX_RETRIEVALS}) exceeded"
            )
        self.retrieval_steps += 1

    def add_generate_invocation(self, input_token_count: int) -> None:
        # Count the invocation before calling model.generate(), so even a
        # failed generate attempt is reflected in llm_calls and prompt_tokens.
        self.llm_calls += 1
        self.prompt_tokens += int(input_token_count)

    def add_completion(self, output_token_count: int) -> None:
        self.completion_tokens += max(0, int(output_token_count))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> Dict[str, Any]:
        return {
            "retrieval_steps": self.retrieval_steps,
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "execution_time_sec": self.execution_time_sec,
        }

def install_generate_wrapper(model: Any) -> None:
    """Wrap model.generate once; all calls are attributed to active tracker."""
    if getattr(model, "_operadic_telemetry_wrapped", False):
        return

    original_generate = model.generate

    def tracked_generate(*args, **kwargs):
        input_ids = kwargs.get("input_ids", None)
        if input_ids is None and args:
            input_ids = args[0]

        tracker = _ACTIVE_TRACKER
        input_count = 0
        if input_ids is not None and hasattr(input_ids, "shape"):
            input_count = int(input_ids.shape[1])

        if tracker is not None:
            tracker.add_generate_invocation(input_count)

        outputs = original_generate(*args, **kwargs)
        sequences = getattr(outputs, "sequences", outputs)
        if (
            tracker is not None
            and input_ids is not None
            and hasattr(sequences, "shape")
            and len(sequences.shape) >= 2
        ):
            new_tokens = int(sequences.shape[1]) - input_count
            tracker.add_completion(max(0, new_tokens))
        return outputs

    model.generate = tracked_generate
    model._operadic_telemetry_wrapped = True

@contextmanager
def activate_tracker(tracker: TelemetryTracker):
    global _ACTIVE_TRACKER
    if _ACTIVE_TRACKER is not None:
        raise RuntimeError("Telemetry trackers cannot be nested.")
    tracker.start()
    _ACTIVE_TRACKER = tracker
    try:
        yield
    finally:
        try:
            tracker.stop()
        finally:
            _ACTIVE_TRACKER = None