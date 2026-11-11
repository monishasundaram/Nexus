import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'nexus.db').as_posix()}")
MODEL_VERSION = "1.0.0"

# Size limits protect the API and the future simulation engine
MAX_NODES = 500
MAX_EDGES = 2000
MAX_EVENTS = 50        # events per scenario
MAX_TIME = 10_000.0    # largest allowed start time or duration (hours)
MAX_MODIFICATIONS = 30  # intervention modifications per scenario