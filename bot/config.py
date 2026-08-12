from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    REMNAWAVE_URL: str
    REMNAWAVE_API_TOKEN: str
    SUBSCRIPTION_HOST: str = ""
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    MIN_TOPUP_RUB: float = 100.0
    WEBHOOK_BASE_URL: str
    WEBHOOK_SECRET: str
    BOT_USERNAME: str
    PRIVACY_URL: str = ""
    USER_AGREEMENT_URL: str = ""
    SSL_CERT_PATH: str = ""
    SSL_KEY_PATH: str = ""
    # Explicit opt-in to running the payment webhook server without TLS.
    # Only for local development — binds 127.0.0.1 instead of all interfaces.
    WEBHOOK_INSECURE_DEV: bool = False

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
