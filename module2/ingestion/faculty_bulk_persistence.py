from __future__ import annotations

from module2.ingestion.faculty_directory import discover_faculty
from module2.ingestion.faculty_profile import discover_profile_components
from module2.ingestion.faculty_persistence import (
    persist_faculty_basic_from_url,
)


def persist_all_faculty() -> None:
    print("Discovering faculty directory...")
    directory_records = discover_faculty()

    print(f"Faculty discovered: {len(directory_records)}")
    print("=" * 80)

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for index, record in enumerate(directory_records, start=1):
        print(
            f"[{index}/{len(directory_records)}] "
            f"{record.name}"
        )

        try:
            # Discover the actual component URLs from the faculty
            # profile page.
            components = discover_profile_components(
                faculty_name=record.name,
                profile_url=record.profile_url,
            )

            if not components.basic_url:
                skipped_count += 1
                print("  SKIPPED: Basic Information URL not found.")
                print()
                continue

            # Persist basic faculty information and its structured
            # child data.
            faculty_id = persist_faculty_basic_from_url(
                faculty_name=record.name,
                profile_url=record.profile_url,
                basic_url=components.basic_url,
            )

            success_count += 1

            print(f"  SUCCESS: faculty_id={faculty_id}")
            print(f"  Basic URL: {components.basic_url}")

        except Exception as exc:
            failed_count += 1
            print(f"  FAILED: {type(exc).__name__}: {exc}")

        print()

    print("=" * 80)
    print("BULK FACULTY PERSISTENCE SUMMARY")
    print("=" * 80)
    print(f"Discovered : {len(directory_records)}")
    print(f"Successful : {success_count}")
    print(f"Skipped    : {skipped_count}")
    print(f"Failed     : {failed_count}")

    if success_count == len(directory_records):
        print()
        print("ALL FACULTY PROFILES PERSISTED SUCCESSFULLY.")


if __name__ == "__main__":
    persist_all_faculty()