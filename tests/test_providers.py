import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.providers import FallbackProvider, LLMProvider, MockProvider, get_default_provider


class _AlwaysExhausted(LLMProvider):
    def _generate_impl(self, prompt: str) -> str:
        raise RuntimeError("no usable model left")


class _Canned(LLMProvider):
    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def _generate_impl(self, prompt: str) -> str:
        return self._text


def test_fallback_provider_uses_first_provider_when_it_works():
    provider = FallbackProvider([_Canned("first"), _Canned("second")])
    assert provider.generate("hi") == "first"
    assert provider.provider_switches == []


def test_fallback_provider_advances_past_an_exhausted_provider():
    provider = FallbackProvider([_AlwaysExhausted(), _Canned("fallback worked")])
    assert provider.generate("hi") == "fallback worked"
    assert provider.provider_switches == ["_AlwaysExhausted"]
    # stays on the working provider for the next call instead of retrying the exhausted one
    assert provider.generate("hi again") == "fallback worked"
    assert provider.provider_switches == ["_AlwaysExhausted"]


def test_fallback_provider_raises_once_every_provider_is_exhausted():
    provider = FallbackProvider([_AlwaysExhausted(), _AlwaysExhausted()])
    try:
        provider.generate("hi")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_get_default_provider_is_mock_with_no_keys_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert isinstance(get_default_provider(), MockProvider)
