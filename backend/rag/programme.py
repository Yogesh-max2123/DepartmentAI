from __future__ import annotations


PHD = "phd"
MTECH = "mtech"
UG = "ug"

PROGRAMME_LABELS = {
    PHD: "Ph.D.",
    MTECH: "M.Tech.",
    UG: "B.Tech.",
}

COMMITTEE_FOR_PROGRAMME = {
    PHD: "DDPC",
    MTECH: "DMPC",
    UG: "DUGC",
}

ORDINANCE_TITLE = {
    PHD: "Ordinances for Doctoral Programmes, 2023",
    MTECH: "Ordinances for Masters' Programmes, 2023",
    UG: "Ordinances for Bachelors Programmes, 2023",
}


def normalize_programme(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return PHD
    compact = text.replace(" ", "").replace("_", "").replace("-", "").replace(".", "")
    if compact in {"ug", "btech", "bachelors", "bachelor", "undergraduate", "dugc"}:
        return UG
    if "bachelor" in text or "b.tech" in text or "btech" in compact or "undergrad" in text:
        return UG
    if compact in {"mtech", "masters", "master", "pg", "dmpc"}:
        return MTECH
    if "master" in text or "m.tech" in text or "mtech" in compact:
        return MTECH
    return PHD


def programme_label(value: str | None) -> str:
    return PROGRAMME_LABELS[normalize_programme(value)]


def committee_name(value: str | None) -> str:
    return COMMITTEE_FOR_PROGRAMME[normalize_programme(value)]


def ordinance_title(value: str | None) -> str:
    return ORDINANCE_TITLE[normalize_programme(value)]
