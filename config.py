from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # File Storage
    upload_dir: str = "/tmp/uploads"  # Vercel uses /tmp for temporary files
    max_file_size: int = 52428800  # 50MB
    session_expiry_hours: int = 24

    # CORS
    cors_origins: str = "*"  # Allow all origins for Vercel

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def upload_path(self) -> Path:
        """Get absolute path for upload directory."""
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
