from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_JSON = (
    BASE_DIR
    / "documents"
    / "phd"
    / "processed"
    / "phd_ordinance_chunks.json"
)

OUTPUT_JSON = (
    BASE_DIR
    / "documents"
    / "phd"
    / "processed"
    / "phd_ordinance_embeddings.json"
)


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
