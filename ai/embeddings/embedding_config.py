import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.programme_paths import get_programme_paths


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_JSON = BASE_DIR / "documents" / "phd" / "processed" / "phd_ordinance_chunks.json"
OUTPUT_JSON = BASE_DIR / "documents" / "phd" / "processed" / "phd_ordinance_embeddings.json"


def apply_programme(programme: str = "phd"):
    global INPUT_JSON, OUTPUT_JSON
    config = get_programme_paths(programme)
    INPUT_JSON = config["chunks_json"]
    OUTPUT_JSON = config["embeddings_json"]
    return config


# ============================================================
# EMBEDDING MODEL
# ============================================================

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


# ============================================================
# GENERATION SETTINGS
# ============================================================

BATCH_SIZE = 16

NORMALIZE_EMBEDDINGS = True
