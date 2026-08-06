from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    REMNAWAVE_URL: str
    REMNAWAVE_API_TOKEN: str
    SUBSCRIPTION_HOST: str = ""
    CRYPTOBOT_TOKEN: str
    LAVA_API_KEY: str = ""
    LAVA_SHOP_ID: str = ""
    FREEKASSA_SHOP_ID: str = ""
    FREEKASSA_SECRET1: str = ""
    FREEKASSA_SECRET2: str = ""
    WEBHOOK_BASE_URL: str
    WEBHOOK_SECRET: str
    BOT_USERNAME: str
    REFERRAL_PERCENT: float = 0.30
    MIN_WITHDRAWAL_RUB: float = 100.0
    PRIVACY_URL: str = ""
    USER_AGREEMENT_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
