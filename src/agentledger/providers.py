"""model provider interface (b8): hosted or local model behind one interface,
plus an offline mock so the pipeline runs with no api key.
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """return the model's raw text completion for a prompt."""


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

    def generate(self, prompt: str) -> str:
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

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def get_default_provider() -> LLMProvider:
    """anthropic if a key is set, else the offline mock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    return MockProvider()
