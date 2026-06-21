from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
  DB_URL: str
  PORT: int = 8000
  APP_NAME: str
  DEBUG: bool = False

  model_config = SettingsConfigDict(env_file=".env")


settings = Settings()