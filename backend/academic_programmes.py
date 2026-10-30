from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDING_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)
EMBEDDING_DIMENSION = 384

PROGRAMME_CORPORA = {
    "UG": {
        "label": "Undergraduate (UG)",
        "source_file": "UG Ordinance.pdf",
        "pdf": PROJECT_ROOT / "documents" / "ug" / "UG Ordinance.pdf",
        "chunks": PROJECT_ROOT
        / "documents"
        / "ug"
        / "processed"
        / "ug_ordinance_chunks.json",
        "structure": PROJECT_ROOT
        / "documents"
        / "ug"
        / "processed"
        / "ug_ordinance_structure.json",
        "embeddings": PROJECT_ROOT
        / "documents"
        / "ug"
        / "processed"
        / "ug_ordinance_embeddings.json",
    },
    "MTECH": {
        "label": "M.Tech. / Masters",
        "source_file": "Ordinances for Masters Programme 2023.pdf",
        "pdf": PROJECT_ROOT
        / "documents"
        / "mtech"
        / "Ordinances for Masters Programme 2023.pdf",
        "chunks": PROJECT_ROOT
        / "documents"
        / "mtech"
        / "processed"
        / "mtech_ordinance_chunks.json",
        "structure": PROJECT_ROOT
        / "documents"
        / "mtech"
        / "processed"
        / "mtech_ordinance_structure.json",
        "embeddings": PROJECT_ROOT
        / "documents"
        / "mtech"
        / "processed"
        / "mtech_ordinance_embeddings.json",
    },
    "PHD": {
        "label": "Doctoral / Ph.D.",
        "source_file": "Ordinances_for_Doctoral_Programm2023.pdf",
        "pdf": PROJECT_ROOT
        / "documents"
        / "phd"
        / "Ordinances_for_Doctoral_Programm2023.pdf",
        "chunks": PROJECT_ROOT
        / "documents"
        / "phd"
        / "processed"
        / "phd_ordinance_chunks.json",
        "structure": PROJECT_ROOT
        / "documents"
        / "phd"
        / "processed"
        / "phd_ordinance_structure.json",
        "embeddings": PROJECT_ROOT
        / "documents"
        / "phd"
        / "processed"
        / "phd_ordinance_embeddings.json",
    },
}


def normalize_programme(programme: str) -> str:
    normalized = programme.strip().upper()
    if normalized not in PROGRAMME_CORPORA:
        raise ValueError(
            f"Unsupported ordinance programme {programme!r}. "
            f"Choose one of: {', '.join(PROGRAMME_CORPORA)}."
        )
    return normalized


def get_programme_corpus(programme: str) -> dict[str, str | Path]:
    return PROGRAMME_CORPORA[normalize_programme(programme)]
