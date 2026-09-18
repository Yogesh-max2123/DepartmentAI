from module2.ingestion.faculty_directory import (
    fetch_directory_html,
    _FacultySectionParser,
    _extract_faculty_records,
)
from module2.ingestion.faculty_profile import discover_profile_components


def main():
    # Discover all faculty from the existing directory parser.
    parser = _FacultySectionParser()
    parser.feed(fetch_directory_html())
    parser.close()

    faculty_records = _extract_faculty_records(parser)

    print(f"Total faculty discovered: {len(faculty_records)}")
    print()

    results = []
    failed = []

    for index, faculty in enumerate(faculty_records, start=1):
        try:
            result = discover_profile_components(
                faculty_name=faculty.name,
                profile_url=faculty.profile_url,
            )

            results.append(result)

            status = "COMPLETE" if result.is_complete else "INCOMPLETE"

            print(
                f"{index:02d}. {faculty.name} -> {status}"
            )

            if not result.is_complete:
                print(
                    "    Missing: "
                    + ", ".join(result.missing_components())
                )

        except Exception as exc:
            failed.append(
                {
                    "name": faculty.name,
                    "profile_url": faculty.profile_url,
                    "error": str(exc),
                }
            )

            print(
                f"{index:02d}. {faculty.name} -> FAILED"
            )
            print(f"    Error: {exc}")

    complete_count = sum(
        result.is_complete for result in results
    )

    incomplete_count = len(results) - complete_count

    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Directory faculty:       {len(faculty_records)}")
    print(f"Profiles processed:      {len(results)}")
    print(f"Complete profiles:       {complete_count}")
    print(f"Incomplete profiles:     {incomplete_count}")
    print(f"Failed profiles:         {len(failed)}")

    if failed:
        print()
        print("FAILED PROFILES:")
        for item in failed:
            print(f"- {item['name']}")
            print(f"  URL: {item['profile_url']}")
            print(f"  Error: {item['error']}")

    print()
    print("Validation finished.")


if __name__ == "__main__":
    main()