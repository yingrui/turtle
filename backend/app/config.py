"""Application configuration.

Settings read from environment with explicit validation_alias names (STOCK_* / DB_URL).
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- Database (discrete fields; URL built in db_url unless DB_URL is set) ---
    database_host: str = Field(default="localhost", validation_alias="STOCK_DATABASE_HOST")
    database_port: int = Field(default=5432, validation_alias="STOCK_DATABASE_PORT")
    database_user: str = Field(default="stock", validation_alias="STOCK_DATABASE_USER")
    database_password: str = Field(default="stock", validation_alias="STOCK_DATABASE_PASSWORD")
    database_name: str = Field(default="stock", validation_alias="STOCK_DATABASE_NAME")
    db_url_override: str | None = Field(default=None, validation_alias="DB_URL")

    tushare_token: str = Field(default="", validation_alias="TUSHARE_TOKEN")
    stock_secret_key: str = Field(
        default="stock-dev-secret-change-in-production", validation_alias="STOCK_SECRET_KEY"
    )
    stock_auth_mode: str = Field(default="local", validation_alias="STOCK_AUTH_MODE")
    stock_allow_signup: bool = Field(default=True, validation_alias="STOCK_ALLOW_SIGNUP")
    stock_local_jwt_exp_hours: int = Field(default=168, validation_alias="STOCK_LOCAL_JWT_EXP_HOURS")
    stock_logs_dir: str = Field(default="/app/logs", validation_alias="STOCK_LOGS_DIR")
    stock_frontend_url: str = Field(default="http://localhost:3200", validation_alias="STOCK_FRONTEND_URL")

    @property
    def db_url(self) -> str:
        """PostgreSQL URL for SQLAlchemy (psycopg2). DB_URL overrides component fields when set."""
        if self.db_url_override:
            return self.db_url_override
        return (
            f"postgresql+psycopg2://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


settings = Settings()
