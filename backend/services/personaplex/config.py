from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "aziza"
    
    # Cache TTLs
    HOT_CACHE_TTL: int = 3600          # 1 hour
    SESSION_TTL: int = 7200            # 2 hours
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
