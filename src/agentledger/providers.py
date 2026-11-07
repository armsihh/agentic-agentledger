"""model provider interface (b8): hosted or local model behind one interface,
plus an offline mock so the pipeline runs with no api key.
"""
from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """base class. tracks call count / latency / char volume for every subclass (E6:
    efficiency & reliability) without each provider having to instrument itself."""

    def __init__(self) -> None:
        self.call_count = 0
        self.total_latency_seconds = 0.0
        self.total_chars_in = 0
        self.total_chars_out = 0

    @abstractmethod
    def _generate_impl(self, prompt: str) -> str:
        """return the model's raw text completion for a prompt."""

    def generate(self, prompt: str) -> str:
        start = time.monotonic()
        text = self._generate_impl(prompt)
        self.call_count += 1
        self.total_latency_seconds += time.monotonic() - start
        self.total_chars_in += len(prompt)
        self.total_chars_out += len(text)
        return text

    def stats(self) -> dict:
        return {
            "call_count": self.call_count,
            "total_latency_seconds": round(self.total_latency_seconds, 3),
            "avg_latency_seconds": round(self.total_latency_seconds / self.call_count, 3) if self.call_count else 0.0,
            "total_chars_in": self.total_chars_in,
            "total_chars_out": self.total_chars_out,
        }


class MockProvider(LLMProvider):
    """deterministic, offline stand-in used by default and by the tests.

    handles the three prompt shapes used by baselines b0/b1: json verdict,
    yes/no per step, and upper/lower half.
    """

    _ERROR_WORDS = re.compile(r"\b(error|fail|exception|incorrect|wrong)\b", re.IGNORECASE)
    _TURN = re.compile(r"\[(\d+)\]\s*(\w+):\s*(.*)")

    def _turns(self, prompt: str) -> list[tuple[int, str, str]]:
        return [(int(s), a, c) for s, a, c in self._TURN.findall(prompt)]

    def _last_error_turn(self, turns: list[tuple[int, str, str]]):
        culprit = None
        for step, agent, content in turns:
            if self._ERROR_WORDS.search(content):
                culprit = (step, agent)
        return culprit

    def _generate_impl(self, prompt: str) -> str:
        if "'Yes' or 'No'" in prompt:
            turns = self._turns(prompt)
            last_content = turns[-1][2] if turns else ""
            return "Yes" if self._ERROR_WORDS.search(last_content) else "No"

        if "'upper half'" in prompt and "'lower half'" in prompt:
            turns = self._turns(prompt)
            culprit = self._last_error_turn(turns)
            if culprit is None or not turns:
                return "lower half"
            mid = turns[0][0] + (turns[-1][0] - turns[0][0]) // 2
            return "upper half" if culprit[0] <= mid else "lower half"

        turns = self._turns(prompt)
        culprit = self._last_error_turn(turns)
        if culprit is None and turns:
            step, agent, _ = turns[-1]
            culprit = (step, agent)
        step, agent = culprit or (0, "unknown")
        return f'{{"agent": "{agent}", "step": {step}, "rationale": "mock provider heuristic"}}'


class AnthropicProvider(LLMProvider):
    """hosted provider. requires ANTHROPIC_API_KEY and the optional anthropic package."""

    def __init__(self, model: str = "claude-sonnet-5-5") -> None:
        super().__init__()
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "install the 'hosted' extra (pip install -e .[hosted]) to use AnthropicProvider"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("set ANTHROPIC_API_KEY to use AnthropicProvider")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def _generate_impl(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


class GroqProvider(LLMProvider):
    """hosted provider on Groq's free-tier API. requires GROQ_API_KEY and the optional groq package.

    each model on the free tier has its own ~200k-tokens/day cap, easy to exhaust across a long
    eval run. rather than fail the whole run, this falls back through a chain of free models,
    advancing whenever one's daily quota is hit (a reliability mechanism in its own right, not
    just a workaround -- the same "retry/recover" behaviour the Phase 2 brief asks the system to
    demonstrate).
    """

    _FALLBACK_CHAIN = [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-safeguard-20b",
        "allam-2-7b",
    ]
    _MIN_GAP_SECONDS = 3.0  # paces calls so a long batch doesn't burst past the free-tier TPM cap
    _last_call_at: float = 0.0

    def __init__(self, model: str | None = None) -> None:
        super().__init__()
        try:
            import groq
        except ImportError as exc:
            raise RuntimeError(
                "install the 'groq' extra (pip install -e .[groq]) to use GroqProvider"
            ) from exc
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("set GROQ_API_KEY to use GroqProvider")
        self._client = groq.Groq(api_key=api_key, timeout=30.0)
        self._models = [model] if model else list(self._FALLBACK_CHAIN)
        self._model_idx = 0
        self.model_switches: list[str] = []  # audit trail: which models this run actually used

    @property
    def _model(self) -> str:
        return self._models[self._model_idx]

    def _generate_impl(self, prompt: str) -> str:
        """calls the free-tier API with pacing + backoff, falling back to the next model on a
        daily-token-quota error (TPD) since that can't clear within any reasonable backoff window."""
        import groq

        while True:
            wait = self._MIN_GAP_SECONDS - (time.monotonic() - GroqProvider._last_call_at)
            if wait > 0:
                time.sleep(wait)

            exhausted = False
            for attempt in range(6):
                try:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    GroqProvider._last_call_at = time.monotonic()
                    return response.choices[0].message.content
                except (groq.RateLimitError, groq.APIStatusError) as exc:
                    message = str(exc).lower()
                    if isinstance(exc, groq.APIStatusError) and "rate_limit" not in message:
                        raise
                    if "tokens per day" in message or " tpd" in message:
                        exhausted = True
                        break
                    time.sleep(min(2 ** attempt, 30))

            if exhausted and self._model_idx + 1 < len(self._models):
                self.model_switches.append(self._model)
                self._model_idx += 1
                continue  # retry immediately on the next model in the chain

            raise RuntimeError(
                f"GroqProvider: no usable model left (tried {self._models[: self._model_idx + 1]}); "
                "all hit their daily quota or kept rate-limiting"
            )

    def stats(self) -> dict:
        base = super().stats()
        base["model"] = self._model
        base["model_switches"] = list(self.model_switches)
        return base


def get_default_provider() -> LLMProvider:
    """anthropic if a key is set, else groq, else the offline mock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    if os.environ.get("GROQ_API_KEY"):
        return GroqProvider()
    return MockProvider()
