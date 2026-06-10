import os
from functools import lru_cache

from google.adk.agents import LlmAgent

from .config import get_settings


@lru_cache(maxsize=1)
def get_agent() -> LlmAgent:
    settings = get_settings()
    if settings.gemini_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)
    model = settings.llm_model or settings.gemini_model
    return LlmAgent(
        name="thinkai",
        model=model,
        instruction=settings.system_prompt,
    )
