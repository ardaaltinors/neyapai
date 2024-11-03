import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "db")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    CHAT_COLLECTION: str = "chat_history"
    USER_COLLECTION: str = "users"
    

settings = Settings()
