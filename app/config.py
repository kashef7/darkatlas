from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
  DB_URL: str
  PORT: int = 8000
  APP_NAME: str
  DEBUG: bool = False
  SECRET_KEY: str
  ALGORITHM: str = "HS256"
  ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

  model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()