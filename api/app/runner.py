import logging
from functools import lru_cache

from google.adk.runners import Runner

from .agent import build_summarizer_llm, get_agent
from .config import get_settings

APP_NAME = "thinkai"

logger = logging.getLogger("thinkai.runner")


def _build_compaction_config():
    """Configura o Context Compaction nativo do ADK.

    Janela deslizante + evento de resumo gerenciados pelo próprio ADK. Fica
    desativado por padrão (`adk_compaction_enabled`) e é totalmente defensivo:
    qualquer falha apenas registra log e segue sem compaction nativa. O
    resumidor segue o provedor ativo (Gemini nativo ou LiteLLM/Ollama).
    """
    settings = get_settings()
    if not settings.adk_compaction_enabled:
        return None
    try:
        from google.adk.apps.app import EventsCompactionConfig
        from google.adk.apps.llm_event_summarizer import LlmEventSummarizer

        summarizer = LlmEventSummarizer(llm=build_summarizer_llm(settings))
        return EventsCompactionConfig(
            summarizer=summarizer,
            compaction_interval=settings.adk_compaction_interval,
            overlap_size=settings.adk_compaction_overlap,
            token_threshold=settings.adk_compaction_token_threshold,
            event_retention_size=settings.adk_compaction_retention,
        )
    except Exception:  # pragma: no cover - depende de ambiente Gemini
        logger.exception("Falha ao configurar Context Compaction nativo do ADK; seguindo sem ele")
        return None


@lru_cache(maxsize=1)
def get_runner() -> Runner:
    from .adk_session import DatabaseSessionService

    session_service = DatabaseSessionService()
    compaction = _build_compaction_config()

    if compaction is not None:
        from google.adk.apps.app import App

        app = App(
            name=APP_NAME,
            root_agent=get_agent(),
            events_compaction_config=compaction,
        )
        logger.info("Runner ADK com Context Compaction nativo habilitado")
        return Runner(app=app, session_service=session_service)

    return Runner(
        app_name=APP_NAME,
        agent=get_agent(),
        session_service=session_service,
    )
