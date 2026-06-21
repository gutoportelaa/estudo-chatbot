import logging
import os
from functools import lru_cache

from google.adk.agents import LlmAgent

from .config import Settings, get_settings

logger = logging.getLogger("thinkai.agent")


def _ollama_api_base(settings: Settings) -> str:
    """LiteLLM espera o host do Ollama sem o sufixo /v1 do OpenAI."""
    base = settings.ollama_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


def _build_model(settings: Settings):
    """Resolve o modelo do agente conforme o provedor.

    - gemini: string de modelo nativa do ADK.
    - ollama/groq/openrouter: `LiteLlm`, mantendo o ADK como orquestrador sem
      depender de chave Gemini. Requer `google-adk[extensions]` (litellm).
    """
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        if settings.gemini_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
            os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)
        return settings.llm_model or settings.gemini_model

    from google.adk.models.lite_llm import LiteLlm

    if provider == "ollama":
        model = settings.llm_model or settings.ollama_model
        return LiteLlm(model=f"ollama_chat/{model}", api_base=_ollama_api_base(settings))

    if provider == "groq":
        if settings.groq_api_key:
            os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)
        model = settings.llm_model or "llama-3.1-8b-instant"
        return LiteLlm(model=f"groq/{model}")

    if provider == "openrouter":
        if settings.openrouter_api_key:
            os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)
        model = settings.llm_model or "meta-llama/llama-3.1-8b-instruct:free"
        return LiteLlm(model=f"openrouter/{model}")

    # Fallback defensivo: trata como string de modelo.
    logger.warning("Provedor LLM desconhecido '%s'; usando como string de modelo", provider)
    return settings.llm_model or settings.gemini_model


def build_summarizer_llm(settings: Settings):
    """Retorna um `BaseLlm` para o resumidor da compaction nativa do ADK.

    Reutiliza a resolução de modelo: para Gemini é uma string (resolvida pelo
    registry), para os demais provedores já é um `LiteLlm` (BaseLlm).
    """
    model = _build_model(settings)
    if isinstance(model, str):
        from google.adk.models.registry import LLMRegistry

        return LLMRegistry.new_llm(model)
    return model


@lru_cache(maxsize=1)
def get_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="thinkai",
        model=_build_model(settings),
        instruction=settings.system_prompt,
    )
