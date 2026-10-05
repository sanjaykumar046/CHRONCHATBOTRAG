import os
from pathlib import Path
from dotenv import load_dotenv

# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv()

# ==========================================================
# Project Base Directory
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================
# Knowledge Base
# ==========================================================

KNOWLEDGE_BASE_PATH = BASE_DIR / os.getenv(
    "KNOWLEDGE_BASE_PATH",
    "knowledge_base"
)

# ==========================================================
# ChromaDB
# ==========================================================

CHROMA_DB_PATH = BASE_DIR / os.getenv(
    "CHROMA_DB_PATH",
    "chroma_db"
)

CHROMA_COLLECTION = os.getenv(
    "CHROMA_COLLECTION",
    "chronai_knowledge"
)

# ==========================================================
# Chunk Settings
# ==========================================================

CHUNK_SIZE = int(
    os.getenv("CHUNK_SIZE", 1000)
)

CHUNK_OVERLAP = int(
    os.getenv("CHUNK_OVERLAP", 200)
)

# ==========================================================
# Retrieval
# ==========================================================

TOP_K_RESULTS = int(
    os.getenv("TOP_K_RESULTS", 5)
)

SIMILARITY_SCORE = float(
    os.getenv("SIMILARITY_SCORE", 0.75)
)

REGISTRY_CANDIDATE_COUNT = int(
    os.getenv("REGISTRY_CANDIDATE_COUNT", 8)
)

# ==========================================================
# Embedding Configuration
# ==========================================================

EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    "http://localhost:11434"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "nomic-embed-text:latest"
)


# ==========================================================
# Ollama Configuration
# ==========================================================

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:3b"
)

# ==========================================================
# AI Response Configuration
# ==========================================================

MAX_RESPONSE_WORDS = int(
    os.getenv("MAX_RESPONSE_WORDS", 100)
)

MAX_RESPONSE_CHARACTERS = int(
    os.getenv("MAX_RESPONSE_CHARACTERS", 600)
)

MAX_RESPONSE_PARAGRAPHS = int(
    os.getenv("MAX_RESPONSE_PARAGRAPHS", 2)
)

MAX_RESPONSE_BULLETS = int(
    os.getenv("MAX_RESPONSE_BULLETS", 4)
)

# ==========================================================
# Logging
# ==========================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000/api"
)
