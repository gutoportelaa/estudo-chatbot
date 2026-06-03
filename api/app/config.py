"""Configurações da aplicação, carregadas de variáveis de ambiente (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    db_path: str = "./data/sessions.sqlite"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
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
