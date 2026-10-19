from module2.ingestion.faculty_directory import discover_faculty
from module2.ingestion.faculty_profile import discover_profile_components
from module2.ingestion.faculty_responsibilities import (
    extract_responsibilities_from_url,
)


def main():
    faculty = discover_faculty()

    print(f"Total faculty discovered: {len(faculty)}")
    print()

    success_count = 0
    incomplete_count = 0
    failed_count = 0

    for index, person in enumerate(faculty, start=1):
        try:
            components = discover_profile_components(
                faculty_name=person.name,
                profile_url=person.profile_url,
            )

            if not components.responsibilities_url:
                print(
                    f"{index:02d}. {person.name} -> "
                    "INCOMPLETE (no responsibilities URL)"
                )
                incomplete_count += 1
                continue

            result = extract_responsibilities_from_url(
                faculty_name=person.name,
                responsibilities_url=components.responsibilities_url,
            )

            has_present = bool(result.present_appointments)
            has_past = bool(result.past_appointments)

            if has_present or has_past:
                print(
                    f"{index:02d}. {person.name} -> COMPLETE "
                    f"(Present: {len(result.present_appointments)}, "
                    f"Past: {len(result.past_appointments)})"
                )
                success_count += 1
            else:
                print(
                    f"{index:02d}. {person.name} -> "
                    "INCOMPLETE (no appointment records)"
                )
                incomplete_count += 1

        except Exception as exc:
            print(
                f"{index:02d}. {person.name} -> "
                f"FAILED ({type(exc).__name__}: {exc})"
            )
            failed_count += 1

    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Directory faculty:       {len(faculty)}")
    print(f"Successful profiles:     {success_count}")
    print(f"Incomplete profiles:     {incomplete_count}")
    print(f"Failed profiles:         {failed_count}")
    print()
    print("Validation finished.")


if __name__ == "__main__":
    main()