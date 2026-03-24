import os
from dotenv import load_dotenv
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))


class Settings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    DATABASE_URL: Optional[str] = None
    RENDER_EXTERNAL_URL: Optional[str] = None
    ADMIN_TOKEN: str = "grimm_admin_secret"
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    QIKINK_CLIENT_ID: Optional[str] = None
    QIKINK_ACCESS_TOKEN: Optional[str] = None
    QIKINK_SANDBOX: bool = True  # flip to False for live
    model_config = SettingsConfigDict(extra="ignore")


try:
    settings = Settings()
    print("Success: Settings loaded from .env")
except Exception as e:
    print(f"Warning: Settings could not be loaded. Error: {e}")
    settings = None
