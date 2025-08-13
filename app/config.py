from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlitecloud://cukrrfslhz.g2.sqlite.cloud:8860/ebf?apikey=tVDakyuw8QkDArjv1Anzno9dBWYNJeipgwW50BhKRus"
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60*60*24*5
    POINT_VALUES: dict = {
        "PRESENCE": 50,
        "BOOK": 20,
        "VERSICLE": 30,
        "PARTICIPATION": 40,
        "GUEST": 10,
        "GAME": 15,
    }

    AGE_GROUPS: dict = {
            "0-6": "Nursery",
            "7-9": "Beginners",
            "10-12": "Intermediate",
            "13-15": "Advanced"
    }

    MAX_DAILY_POINTS: int = 165

    class Config:
        env_file = ".env"

settings = Settings()
