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
    """hosted provider on Groq's free-tier API. requires GROQ_API_KEY and the optional groq package."""

    _MIN_GAP_SECONDS = 3.0  # paces calls so a long batch doesn't burst past the free-tier TPM cap
    _last_call_at: float = 0.0

    def __init__(self, model: str = "qwen/qwen3.8-27b") -> None:
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
        self._model = model

    def _generate_impl(self, prompt: str) -> str:
        """calls the free-tier API with pacing + backoff on rate limits, since eval runs make many calls.

        a daily-token-quota error (TPD) won't clear within any reasonable backoff window, so it
        fails fast instead of burning ~3-5 minutes of retries per call before giving up anyway.
        """
        import groq

        wait = self._MIN_GAP_SECONDS - (time.monotonic() - GroqProvider._last_call_at)
        if wait > 0:
            time.sleep(wait)

        for attempt in range(10):
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
                    raise RuntimeError(
                        f"GroqProvider: daily token quota exhausted for model '{self._model}' - "
                        f"switch models (quotas are per-model) or wait for it to reset: {exc}"
                    ) from exc
                time.sleep(min(2 ** attempt, 30))
        raise RuntimeError("GroqProvider: rate-limited after repeated retries")


def get_default_provider() -> LLMProvider:
    """anthropic if a key is set, else groq, else the offline mock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    if os.environ.get("GROQ_API_KEY"):
        return GroqProvider()
    return MockProvider()
