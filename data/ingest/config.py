from pathlib import Path

from app.config import settings

DATA_DIR = Path(__file__).resolve().parent.parent
MARKDOWN_DIR = DATA_DIR / "Markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"
CHUNK_MAX_TOKENS = 800
EMBEDDING_DIMENSIONS = settings.gemini_embedding_dimensions