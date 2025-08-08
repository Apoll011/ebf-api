from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./database.db"
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    POINT_VALUES: dict = {
        "PRESENCE": 50,
        "BOOK": 20,
        "VERSICLE": 30,
        "PARTICIPATION": 40,
        "GUEST": 10,
        "GAME": 15,
    }

    class Config:
        env_file = ".env"

settings = Settings()
