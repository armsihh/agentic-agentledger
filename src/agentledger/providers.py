"""Model provider interface (B8): one hosted LLM and one local model behind the same
interface, plus a deterministic offline mock so the pipeline runs without any API key.
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's raw text completion for a prompt."""


class MockProvider(LLMProvider):
    """Deterministic, offline stand-in used by default and by the tests.

    Heuristic only: picks the last agent turn whose content mentions an error
    keyword, so `eval/run_baseline.py` and the test suite can run end-to-end
    with no network access and no API key.
    """

    _ERROR_WORDS = re.compile(r"\b(error|fail|exception|incorrect|wrong)\b", re.IGNORECASE)

    def generate(self, prompt: str) -> str:
        turns = re.findall(r"\[(\d+)\]\s*(\w+):\s*(.*)", prompt)
        culprit = None
        for step, agent, content in turns:
            if self._ERROR_WORDS.search(content):
                culprit = (int(step), agent)
        if culprit is None and turns:
            step, agent, _ = turns[-1]
            culprit = (int(step), agent)
        step, agent = culprit or (0, "unknown")
        return f'{{"agent": "{agent}", "step": {step}, "rationale": "mock provider heuristic"}}'


class AnthropicProvider(LLMProvider):
    """Hosted provider. Requires ANTHROPIC_API_KEY and the optional `anthropic` package."""

    def __init__(self, model: str = "claude-sonnet-5-5") -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
            raise RuntimeError(
                "Install the 'hosted' extra (pip install -e .[hosted]) to use AnthropicProvider"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Set ANTHROPIC_API_KEY to use AnthropicProvider")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def get_default_provider() -> LLMProvider:
    """Pick AnthropicProvider when a key is configured, else fall back to the mock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    return MockProvider()
