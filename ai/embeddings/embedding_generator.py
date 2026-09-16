import json
import sys
from datetime import datetime

from sentence_transformers import SentenceTransformer

from embedding_config import (
    INPUT_JSON,
    OUTPUT_JSON,
    MODEL_NAME,
    BATCH_SIZE,
    NORMALIZE_EMBEDDINGS,
)


# ============================================================
# LOAD CHUNKS
# ============================================================

def load_chunks():
    print("Loading chunked knowledge base...")

    if not INPUT_JSON.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_JSON}"
        )

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])

    if not chunks:
        raise ValueError("No chunks found in input JSON.")

    print(f"Chunks loaded      : {len(chunks)}")

    return data, chunks


# ============================================================
# BUILD EMBEDDING TEXT
# ============================================================

def build_embedding_text(chunk):
    """
    Add important metadata to the text being embedded.
    """

    document = chunk.get("document", "MNNIT Masters' Ordinance")
    section = chunk.get("section")
    clause = chunk.get("clause")
    page_start = chunk.get("page_start")
    page_end = chunk.get("page_end")
    text = chunk.get("text", "")

    parts = [
        f"Document: {document}"
    ]

    if section:
        parts.append(f"Section: {section}")

    if clause:
        parts.append(f"Clause: {clause}")

    if page_start:
        if page_end and page_end != page_start:
            parts.append(f"Pages: {page_start}-{page_end}")
        else:
            parts.append(f"Page: {page_start}")

    parts.append("")
    parts.append(text)

    return "\n".join(parts)


# ============================================================
# VALIDATE CHUNKS
# ============================================================

def validate_chunks(chunks):
    print("\nValidating chunks before embedding...")

    errors = []

    for index, chunk in enumerate(chunks):

        if not chunk.get("chunk_id"):
            errors.append(
                f"Chunk {index}: missing chunk_id"
            )

        if not chunk.get("text"):
            errors.append(
                f"Chunk {index}: missing text"
            )

        if chunk.get("page_start") is None:
            errors.append(
                f"Chunk {index}: missing page_start"
            )

        if chunk.get("page_end") is None:
            errors.append(
                f"Chunk {index}: missing page_end"
            )

    if errors:
        print("\nVALIDATION FAILED")

        for error in errors:
            print(f" - {error}")

        raise ValueError(
            f"{len(errors)} chunk validation errors found."
        )

    print("Chunk validation   : PASS")


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

def load_model():
    print("\nLoading embedding model...")
    print(f"Model              : {MODEL_NAME}")

    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as exc:
        print("\nERROR: Could not load embedding model.")
        print(exc)
        print(
            "\nMake sure your virtual environment is active "
            "and the required packages are installed."
        )
        sys.exit(1)

    dimension = model.get_sentence_embedding_dimension()

    print(f"Vector dimension    : {dimension}")
    print("Embedding model     : READY")

    return model, dimension


# ============================================================
# GENERATE EMBEDDINGS
# ============================================================

def generate_embeddings(model, chunks):
    print("\nGenerating embeddings...")
    print(f"Batch size          : {BATCH_SIZE}")

    texts = [
        build_embedding_text(chunk)
        for chunk in chunks
    ]

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=NORMALIZE_EMBEDDINGS,
    )

    return embeddings


# ============================================================
# VALIDATE EMBEDDINGS
# ============================================================

def validate_embeddings(embeddings, chunks, dimension):
    print("\nValidating generated embeddings...")

    errors = []

    if len(embeddings) != len(chunks):
        errors.append(
            f"Vector count ({len(embeddings)}) != "
            f"chunk count ({len(chunks)})"
        )

    for index, vector in enumerate(embeddings):

        if len(vector) != dimension:
            errors.append(
                f"Chunk {index}: incorrect vector dimension "
                f"{len(vector)}"
            )

        if not all(float(value) == float(value) for value in vector):
            errors.append(
                f"Chunk {index}: NaN detected"
            )

        if not all(
            abs(float(value)) != float("inf")
            for value in vector
        ):
            errors.append(
                f"Chunk {index}: Infinity detected"
            )

    if errors:
        print("\nEMBEDDING VALIDATION FAILED")

        for error in errors[:20]:
            print(f" - {error}")

        if len(errors) > 20:
            print(
                f" ... and {len(errors) - 20} more errors"
            )

        raise ValueError(
            f"{len(errors)} embedding validation errors found."
        )

    print("Vector count       : PASS")
    print("Vector dimensions  : PASS")
    print("NaN check          : PASS")
    print("Infinity check     : PASS")


# ============================================================
# BUILD OUTPUT
# ============================================================

def build_output(source_data, chunks, embeddings, dimension):
    print("\nBuilding embedding knowledge base...")

    embedded_chunks = []

    for chunk, vector in zip(chunks, embeddings):

        embedded_chunk = dict(chunk)

        embedded_chunk["embedding_text"] = build_embedding_text(
            chunk
        )

        embedded_chunk["embedding"] = vector.tolist()

        embedded_chunk["embedding_dimension"] = dimension

        embedded_chunks.append(embedded_chunk)

    output = {
        "document": source_data.get(
            "document",
            "MNNIT Masters' Ordinance"
        ),

        "embedding_model": MODEL_NAME,

        "embedding_dimension": dimension,

        "normalized": NORMALIZE_EMBEDDINGS,

        "total_chunks": len(embedded_chunks),

        "generated_at": datetime.now().isoformat(),

        "chunks": embedded_chunks,
    }

    return output


# ============================================================
# SAVE OUTPUT
# ============================================================

def save_output(output):
    print("\nSaving embeddings...")

    OUTPUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Output: {OUTPUT_JSON}")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("MNNIT MASTERS' ORDINANCE - EMBEDDING GENERATOR")
    print("=" * 60)

    # 1. Load chunks
    source_data, chunks = load_chunks()

    # 2. Validate chunks
    validate_chunks(chunks)

    # 3. Load model
    model, dimension = load_model()

    # 4. Generate embeddings
    embeddings = generate_embeddings(
        model,
        chunks
    )

    # 5. Validate vectors
    validate_embeddings(
        embeddings,
        chunks,
        dimension
    )

    # 6. Build output
    output = build_output(
        source_data,
        chunks,
        embeddings,
        dimension
    )

    # 7. Save
    save_output(output)

    print("\n" + "=" * 60)
    print("EMBEDDING GENERATION COMPLETE")
    print("=" * 60)

    print(f"Chunks embedded    : {len(chunks)}")
    print(f"Vector dimension    : {dimension}")
    print(f"Model               : {MODEL_NAME}")
    print("Validation          : PASS")
    print(f"Output              : {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
