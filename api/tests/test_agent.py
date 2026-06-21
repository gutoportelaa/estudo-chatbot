"""Testes da resolução de modelo por provedor (agent.py), sem acessar a rede."""

from __future__ import annotations

from app.agent import _build_model, _ollama_api_base
from app.config import Settings


def _settings(**over) -> Settings:
    return Settings(**over)


def test_ollama_api_base_strips_v1_suffix():
    s = _settings(ollama_base_url="http://localhost:11434/v1")
    assert _ollama_api_base(s) == "http://localhost:11434"


def test_ollama_api_base_without_v1():
    s = _settings(ollama_base_url="http://host:11434/")
    assert _ollama_api_base(s) == "http://host:11434"


def test_gemini_returns_model_string():
    s = _settings(llm_provider="gemini", gemini_model="gemini-2.0-flash")
    assert _build_model(s) == "gemini-2.0-flash"


def test_ollama_returns_litellm_with_prefix():
    from google.adk.models.lite_llm import LiteLlm

    s = _settings(llm_provider="ollama", ollama_model="llama3.2:3b")
    model = _build_model(s)
    assert isinstance(model, LiteLlm)
    assert model.model == "ollama_chat/llama3.2:3b"


def test_groq_returns_litellm_with_prefix():
    from google.adk.models.lite_llm import LiteLlm

    s = _settings(llm_provider="groq", llm_model="llama-3.1-8b-instant")
    model = _build_model(s)
    assert isinstance(model, LiteLlm)
    assert model.model == "groq/llama-3.1-8b-instant"
