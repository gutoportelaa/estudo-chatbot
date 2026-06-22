"""Configurações da aplicação, carregadas de variáveis de ambiente (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco de dados
    database_url: str = "postgresql+asyncpg://thinkai:thinkai@localhost:5432/thinkai"

    # Provedor LLM: gemini | groq | openrouter | ollama
    llm_provider: str = "gemini"
    llm_model: str = ""  # deixe vazio para usar o padrão do provedor

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # mantido para compatibilidade

    # Groq
    groq_api_key: str = ""

    # OpenRouter
    openrouter_api_key: str = ""

    # Ollama (local)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"

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

    # ----- Gestão de histórico (janela deslizante + sumarização híbrida) -----
    # Estratégia: "hybrid" (buffer recente + resumo), "window" (só janela), "off".
    history_strategy: str = "hybrid"
    # N mensagens recentes mantidas verbatim na janela.
    history_window_messages: int = 12
    # Quantas mensagens precisam sair da janela para disparar uma compactação.
    history_summarize_after_messages: int = 6
    # Limiar de tokens do resumo: acima disso, recompacta (resumo-de-resumo).
    history_summary_max_tokens: int = 600
    # Modelo usado para sumarizar (vazio = mesmo modelo do chat).
    summarizer_model: str = ""

    # ----- Context Compaction nativo do ADK (caminho Gemini) -----
    adk_compaction_enabled: bool = False
    adk_compaction_interval: int = 4
    adk_compaction_overlap: int = 1
    adk_compaction_token_threshold: int = 4000
    adk_compaction_retention: int = 6

    # ----- Armazenamento de documentos (PDFs) -----
    # Backend: "local" (filesystem, ideal p/ dev) | "s3" (produção)
    storage_backend: str = "local"
    # Diretório-raiz quando storage_backend = "local".
    storage_dir: str = "./data/documents"
    # Tamanho máximo de upload, em MB (RF-002).
    max_upload_mb: int = 50
    # S3 (storage_backend = "s3")
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    # Validade das presigned URLs, em segundos.
    presign_expire_seconds: int = 900

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
