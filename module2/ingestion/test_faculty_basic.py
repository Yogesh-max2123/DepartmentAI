from module2.ingestion.faculty_directory import (
    fetch_directory_html,
    _FacultySectionParser,
    _extract_faculty_records,
)

from module2.ingestion.faculty_profile import (
    discover_profile_components,
)

from module2.ingestion.faculty_basic import (
    extract_basic_profile_from_url,
)


def discover_faculty():
    """Discover all faculty from the official MNNIT CSE directory."""

    html = fetch_directory_html()

    parser = _FacultySectionParser()
    parser.feed(html)
    parser.close()

    return _extract_faculty_records(parser)


def main():
    faculty_records = discover_faculty()

    print(f"Total faculty discovered: {len(faculty_records)}")
    print()

    successful = 0
    failed = 0
    incomplete = 0

    for index, faculty in enumerate(faculty_records, start=1):
        print(f"{index:02d}. {faculty.name}")

        try:
            # Discover the actual component URLs from the
            # faculty's main profile page.
            components = discover_profile_components(
                faculty_name=faculty.name,
                profile_url=faculty.profile_url,
            )

            if not components.basic_url:
                incomplete += 1
                print("    Basic Information URL: MISSING")
                print("    Status: INCOMPLETE")
                print()
                continue

            # Fetch and parse the actual Basic Information page.
            data = extract_basic_profile_from_url(
                faculty_name=faculty.name,
                basic_url=components.basic_url,
            )

            print(f"    Basic URL: {components.basic_url}")
            print(f"    Parsed name: {data.faculty_name or '-'}")
            print(f"    Designation: {data.designation or '-'}")
            print(f"    Current courses: {len(data.current_courses)}")
            print(f"    Past courses: {len(data.past_courses)}")
            print(f"    Education: {len(data.education)}")
            print(f"    Research areas: {len(data.research_areas)}")
            print(f"    Memberships: {len(data.memberships)}")
            print(f"    Research IDs: {len(data.research_ids)}")

            successful += 1
            print("    Status: SUCCESS")

        except Exception as exc:
            failed += 1
            print("    Status: FAILED")
            print(f"    Error: {exc}")

        print()

    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Directory faculty: {len(faculty_records)}")
    print(f"Successful:        {successful}")
    print(f"Incomplete:        {incomplete}")
    print(f"Failed:            {failed}")
    print()
    print("Validation finished.")


if __name__ == "__main__":
    main()