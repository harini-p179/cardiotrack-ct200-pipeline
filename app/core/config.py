import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    PROJECT_NAME: str = "CardioTrack CT-200 Document Pipeline"
    API_V1_STR: str = "/api"
    
    # SQLite Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ct200_pipeline.db")
    
    # NoSQL Storage: "json" or "mongodb"
    NOSQL_STORE: str = os.getenv("NOSQL_STORE", "json")
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "ct200_qa_testcases")
    
    # Local JSON document store path
    JSON_STORE_PATH: str = os.getenv(
        "JSON_STORE_PATH", 
        str(BASE_DIR / "data" / "test_cases_store.json")
    )
    
    # Gemini API Key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Path to PDFs
    DATA_DIR: Path = BASE_DIR / "data"
    V1_PDF_PATH: Path = DATA_DIR / "ct200_manual.pdf"
    V2_PDF_PATH: Path = DATA_DIR / "ct200_manual_v2.pdf"

settings = Settings()
