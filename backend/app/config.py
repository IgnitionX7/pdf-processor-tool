from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # File Storage
    upload_dir: str = "../uploads"
    max_file_size: int = 52428800  # 50MB
    session_expiry_hours: int = 24

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def upload_path(self) -> Path:
        """Get absolute path for upload directory."""
        # On Vercel (serverless), use /tmp directory as it's the only writable location
        # Detect Vercel environment by checking for VERCEL env variable
        if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            path = Path("/tmp/uploads")
        else:
            path = Path(__file__).parent.parent / self.upload_dir

        # Only create directory if it doesn't exist (avoid errors on read-only filesystems)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            # If we can't create it, assume it exists or will be created on first use
            pass

        return path.resolve()

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
