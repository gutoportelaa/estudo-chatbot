from functools import lru_cache

from google.adk.runners import Runner

from .agent import get_agent

APP_NAME = "thinkai"


@lru_cache(maxsize=1)
def get_runner() -> Runner:
    from .adk_session import DatabaseSessionService

    return Runner(
        app_name=APP_NAME,
        agent=get_agent(),
        session_service=DatabaseSessionService(),
    )
