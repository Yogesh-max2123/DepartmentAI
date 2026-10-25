from pathlib import Path

from module2.ingestion.faculty_directory import discover_faculty
from module2.ingestion.faculty_profile import discover_profile_components
from module2.ingestion.faculty_responsibilities import (
    fetch_responsibilities_html,
)


INCOMPLETE_FACULTY = {
    "Dr. Kapil",
    "Dr. Neelam Dayal",
    "Dr. Himanshu Nandanwar",
    "Dr. Divyansh Thakur",
    "Dr. Archana Ojha",
    "Dr. Shubhangi Chaturvedi",
    "Dr. Rashmi Maheshwari",
    "Dr. Shreeya Swagatika Sahoo",
    "Dr. Komal Gupta",
    "Dr. K. Sowjanya",
    "Dr. Satarupa Chakrabarti",
}


def main():
    faculty = discover_faculty()

    output_dir = Path(
        "module2/ingestion/debug_responsibilities"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    inspected = 0

    for person in faculty:
        if person.name not in INCOMPLETE_FACULTY:
            continue

        print(f"\nInspecting: {person.name}")

        components = discover_profile_components(
            faculty_name=person.name,
            profile_url=person.profile_url,
        )

        if not components.responsibilities_url:
            print("  Responsibilities URL: MISSING")
            continue

        print(
            f"  Responsibilities URL: "
            f"{components.responsibilities_url}"
        )

        html = fetch_responsibilities_html(
            components.responsibilities_url
        )

        safe_name = (
            person.name
            .replace(".", "")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
            .replace(" ", "_")
        )

        output_file = (
            output_dir / f"{safe_name}.html"
        )

        output_file.write_text(
            html,
            encoding="utf-8",
        )

        print(f"  Saved: {output_file}")

        inspected += 1

    print()
    print("=" * 60)
    print(f"HTML files saved: {inspected}")
    print("=" * 60)


if __name__ == "__main__":
    main()