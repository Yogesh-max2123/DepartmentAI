from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests


PARENT_URL = "https://mnnit.ac.in/index.php/department/engineering/csed#publications"

COMPONENT_LABELS = {
    "Basic Information": "basic_url",
    "Responsibilities": "responsibilities_url",
    "Research Publications": "publications_url",
    "Other Academic Achievements": "achievements_url",
    "Thesis Supervised": "thesis_url",
}


@dataclass
class FacultyProfileComponents:
    faculty_name: str
    profile_url: str
    basic_url: str = ""
    responsibilities_url: str = ""
    publications_url: str = ""
    achievements_url: str = ""
    thesis_url: str = ""

    def missing_components(self) -> list[str]:
        missing = []

        if not self.basic_url:
            missing.append("Basic Information")

        if not self.responsibilities_url:
            missing.append("Responsibilities")

        if not self.publications_url:
            missing.append("Research Publications")

        if not self.achievements_url:
            missing.append("Other Academic Achievements")

        if not self.thesis_url:
            missing.append("Thesis Supervised")

        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_components()


class _ProfileLinkParser(HTMLParser):
    """
    Collect anchors from an individual faculty profile page.
    """

    def __init__(self):
        super().__init__()
        self.links = []

        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attributes = dict(attrs)
        self._current_href = attributes.get("href")
        self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return

        if self._current_href is not None:
            text = " ".join("".join(self._current_text).split())

            self.links.append(
                {
                    "text": text,
                    "href": self._current_href,
                }
            )

        self._current_href = None
        self._current_text = []


def fetch_profile_html(profile_url: str) -> str:
    """
    Fetch the HTML of one faculty's main profile page.
    """

    response = requests.get(
        profile_url,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def _normalize_url(profile_url: str, href: str | None) -> str:
    """
    Convert a discovered relative/absolute href into an absolute URL.
    """

    if not href:
        return ""

    return urljoin(profile_url, href.strip())


def _normalize_label(text: str) -> str:
    """
    Normalize anchor text for reliable component matching.
    """

    return " ".join(text.split()).strip().lower()


def extract_profile_components(
    faculty_name: str,
    profile_url: str,
    html: str,
) -> FacultyProfileComponents:
    """
    Extract the five component URLs from one faculty profile page.

    Component URLs are discovered from the actual navigation links
    present on the profile page. No URL pattern is assumed.
    """

    parser = _ProfileLinkParser()
    parser.feed(html)
    parser.close()

    result = FacultyProfileComponents(
        faculty_name=faculty_name,
        profile_url=profile_url,
    )

    label_to_field = {
        label.lower(): field
        for label, field in COMPONENT_LABELS.items()
    }

    for link in parser.links:
        label = _normalize_label(link["text"])

        if label not in label_to_field:
            continue

        field_name = label_to_field[label]

        # Keep the first valid occurrence.
        if getattr(result, field_name):
            continue

        component_url = _normalize_url(
            profile_url,
            link["href"],
        )

        setattr(
            result,
            field_name,
            component_url,
        )

    return result


def discover_profile_components(
    faculty_name: str,
    profile_url: str,
) -> FacultyProfileComponents:
    """
    Fetch and discover the five component URLs for one faculty profile.
    """

    html = fetch_profile_html(profile_url)

    return extract_profile_components(
        faculty_name=faculty_name,
        profile_url=profile_url,
        html=html,
    )


if __name__ == "__main__":
    faculty_name = "Prof. M.M.Gore"
    profile_url = "https://mnnit.ac.in/profile/gore"

    result = discover_profile_components(
        faculty_name,
        profile_url,
    )

    print(f"Faculty: {result.faculty_name}")
    print(f"Profile: {result.profile_url}")
    print()

    print(f"Basic Information: {result.basic_url}")
    print(f"Responsibilities: {result.responsibilities_url}")
    print(f"Research Publications: {result.publications_url}")
    print(f"Other Academic Achievements: {result.achievements_url}")
    print(f"Thesis Supervised: {result.thesis_url}")
    print()

    print(f"Complete: {result.is_complete}")

    if result.missing_components():
        print("Missing:", ", ".join(result.missing_components()))