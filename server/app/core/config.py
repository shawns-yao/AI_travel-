from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://travel:travel@localhost:5432/travel"
    redis_url: str = "redis://localhost:6379"
    qweather_api_key: str = ""
    dashscope_api_key: str = ""
    jwt_secret: str = "dev-secret-change-in-production"
    embedding_model: str = "text-embedding-v3"
    chat_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Agent runtime
    agent_timeout_seconds: int = 120
    tool_timeout_seconds: int = 30
    max_retries: int = 3

    # Memory
    short_term_ttl_seconds: int = 3600
    long_term_top_k: int = 10
    long_term_min_confidence: float = 0.5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
