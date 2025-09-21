# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # DB (if you want Mongo later, replace LocalStorage)
    MONGODB_URI = os.getenv('MONGODB_URI', '')
    DATABASE_NAME = "resume_relevance_db"

    # Embeddings & FAISS
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', "all-MiniLM-L6-v2")
    FAISS_PERSIST_DIR = os.getenv('FAISS_PERSIST_DIR', "./faiss_data")

    # Optional cloud API key (not required for local demo)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

    # Collections / file names
    RESUMES_COLLECTION = "resumes"
    JOBS_COLLECTION = "job_descriptions"
    EVALUATIONS_COLLECTION = "evaluations"

    # Scoring weights (these should sum to 1.0 but the engine normalizes if they don't)
    HARD_MATCH_WEIGHT = float(os.getenv('HARD_MATCH_WEIGHT', 0.4))
    SOFT_MATCH_WEIGHT = float(os.getenv('SOFT_MATCH_WEIGHT', 0.6))

    # MCQ verification: maximum additive boost (in absolute score points, 0-100)
    MCQ_MAX_BOOST = float(os.getenv('MCQ_MAX_BOOST', 10.0))

    # Thresholds for verdicts (0-100)
    HIGH_THRESHOLD = float(os.getenv('HIGH_THRESHOLD', 75.0))
    MEDIUM_THRESHOLD = float(os.getenv('MEDIUM_THRESHOLD', 50.0))

    # Other flags
    USE_LOCAL_DB = True