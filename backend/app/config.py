
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Groq Configuration
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # Database Configuration
    database_url: str = "sqlite:///./resolveai.db"

        # Qdrant Configuration
    qdrant_path: str = "./data/qdrant"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "resolveai_knowledge"

    # Embedding Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # RAG Configuration
    chunk_size: int = 700
    chunk_overlap: int = 100
    similarity_threshold: float = 0.35
    top_k: int = 5

        # Document Upload Configuration
    max_upload_mb: int = 10

    # Request Body Configuration
    max_request_body_mb: int = 12

    # CORS Configuration
    cors_origins: str = "http://localhost:5173"

    # JWT Authentication Configuration
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Initial Admin Configuration
    admin_email: str = ""
    admin_password: str = ""
    admin_full_name: str = "ResolveAI Admin"

    @model_validator(mode="after")
    def validate_security_settings(self):

        if len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must contain at least 32 characters"
            )

        if self.jwt_algorithm != "HS256":
            raise ValueError(
                "JWT_ALGORITHM must be HS256"
            )

        if not 1 <= self.access_token_expire_minutes <= 1440:
            raise ValueError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440"
            )

        if self.max_upload_mb < 1:
            raise ValueError(
                "MAX_UPLOAD_MB must be at least 1"
            )

        if self.max_request_body_mb < 1:
            raise ValueError(
                "MAX_REQUEST_BODY_MB must be at least 1"
            )

        if self.max_request_body_mb <= self.max_upload_mb:
            raise ValueError(
                "MAX_REQUEST_BODY_MB must be greater than MAX_UPLOAD_MB"
            )

        return self


    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
