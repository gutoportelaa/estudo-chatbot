"""Configurações da aplicação, carregadas de variáveis de ambiente (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco de dados
    database_url: str = "postgresql+asyncpg://thinkai:thinkai@localhost:5432/thinkai"

    # Provedor LLM: gemini | groq | openrouter
    llm_provider: str = "gemini"
    llm_model: str = ""  # deixe vazio para usar o padrão do provedor

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # mantido para compatibilidade

    # Groq
    groq_api_key: str = ""

    # OpenRouter
    openrouter_api_key: str = ""

    # Auth / JWT
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 horas

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # System prompt do agente
    system_prompt: str = (
        "Você é o ThinkAI, um assistente prestativo, claro e conciso. "
        "Responda no mesmo idioma da pergunta."
    )

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
