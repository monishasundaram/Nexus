import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'nexus.db').as_posix()}")
MODEL_VERSION = "1.0.0"

# Size limits protect the API and the future simulation engine
MAX_NODES = 500
MAX_EDGES = 2000