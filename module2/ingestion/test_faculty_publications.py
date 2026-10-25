from pathlib import Path

from module2.ingestion.faculty_publications import (
    parse_publication_pdf,
)


PDF_DIR = Path(
    "module2/ingestion/debug_publication_structures/pdf"
)


REPRESENTATIVE_PDFS = {
    "Prof. M.M.Gore": "prof_m_m_gore.pdf",
    "Prof. D.S. Kushwaha": "prof_d_s_kushwaha.pdf",
    "Dr. Shashank Srivastava": "dr_shashank_srivastava.pdf",
    "Dr. Vibhav Prakash Singh": "dr_vibhav_prakash_singh.pdf",
    "Dr. Abhinav Kumar": "dr_abhinav_kumar.pdf",
    "Dr. Satarupa Chakrabarti": "dr_satarupa_chakrabarti.pdf",
}


def main() -> None:
    print("=" * 70)
    print("PUBLICATION PARSER TEST")
    print("=" * 70)
    print()

    total_records = 0

    for faculty_name, filename in REPRESENTATIVE_PDFS.items():
        pdf_path = PDF_DIR / filename

        print(f"Faculty: {faculty_name}")
        print(f"PDF: {pdf_path}")

        if not pdf_path.exists():
            print("  ERROR: PDF not found")
            print()
            continue

        try:
            records = parse_publication_pdf(
                pdf_path=pdf_path,
                faculty_name=faculty_name,
            )

            print(f"  Records extracted: {len(records)}")

            type_counts: dict[str, int] = {}

            for record in records:
                type_counts[record.publication_type] = (
                    type_counts.get(
                        record.publication_type,
                        0,
                    )
                    + 1
                )

            print(f"  Types: {type_counts}")

            for index, record in enumerate(
                records[:5],
                start=1,
            ):
                print(
                    f"  {index}. "
                    f"[{record.publication_type}] "
                    f"{record.title[:120]}"
                )

                if record.publication_year:
                    print(
                        f"     Year: "
                        f"{record.publication_year}"
                    )

                if record.doi:
                    print(
                        f"     DOI: "
                        f"{record.doi}"
                    )

            total_records += len(records)

        except Exception as exc:
            print(
                f"  ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

        print()

    print("=" * 70)
    print(
        f"TOTAL RECORDS EXTRACTED: {total_records}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()