from dataclasses import dataclass, field
from html.parser import HTMLParser

import requests


@dataclass
class FacultyResponsibilitiesData:
    """
    Structured data extracted from one faculty member's
    Responsibilities page.
    """

    faculty_name: str = ""

    present_appointments: list[str] = field(
        default_factory=list
    )

    past_appointments: list[str] = field(
        default_factory=list
    )


class _ResponsibilitiesParser(HTMLParser):
    """
    Parser for the actual MNNIT Responsibilities page structure.

    The source uses:

        <h2>Present Appointments Held</h2>
        <dl>
            <dd>...</dd>
            <dd>...</dd>
        </dl>

        <h2>Past Appointments Held</h2>
        <dl>
            <dd>...</dd>
            <dd>...</dd>
        </dl>

    The complete text of each <dd> is preserved as source-derived
    responsibility information.
    """

    def __init__(self):
        super().__init__()

        # --------------------------------------------------------------
        # Faculty name
        # --------------------------------------------------------------
        self.faculty_name = ""

        # --------------------------------------------------------------
        # Extracted responsibility data
        # --------------------------------------------------------------
        self.present_appointments = []
        self.past_appointments = []

        # --------------------------------------------------------------
        # Current section
        # --------------------------------------------------------------
        self.section = ""

        # --------------------------------------------------------------
        # Current <h1>/<h2>/<dd> text
        # --------------------------------------------------------------
        self.current_heading_parts = []
        self.current_dd_parts = []

        # --------------------------------------------------------------
        # HTML state
        # --------------------------------------------------------------
        self.in_h1 = False
        self.in_h2 = False
        self.in_dd = False

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "h1":
            self.in_h1 = True
            self.current_heading_parts = []

        elif tag == "h2":
            self.in_h2 = True
            self.current_heading_parts = []

        elif tag == "dd":
            self.in_dd = True
            self.current_dd_parts = []

    def handle_data(self, data):
        text = " ".join(data.split())

        if not text:
            return

        if self.in_h1:
            self.faculty_name = (
                f"{self.faculty_name} {text}".strip()
            )

        if self.in_h2:
            self.current_heading_parts.append(text)

        if self.in_dd:
            self.current_dd_parts.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "h1":
            self.in_h1 = False

            self.faculty_name = " ".join(
                self.faculty_name.split()
            )

        elif tag == "h2":
            self.in_h2 = False

            heading = " ".join(
                self.current_heading_parts
            ).strip()

            self._set_section(heading)

            self.current_heading_parts = []

        elif tag == "dd":
            self.in_dd = False

            text = " ".join(
                self.current_dd_parts
            ).strip()

            if text:
                self._process_appointment(text)

            self.current_dd_parts = []

    # ------------------------------------------------------------------
    # Section handling
    # ------------------------------------------------------------------

    def _set_section(self, heading):
        """
        Set the active parsing section from an <h2> heading.
        """

        normalized = " ".join(
            heading.split()
        ).strip().lower()

        if normalized == "present appointments held":
            self.section = "present"

        elif normalized == "past appointments held":
            self.section = "past"

        else:
            self.section = ""

    # ------------------------------------------------------------------
    # Appointment extraction
    # ------------------------------------------------------------------

    def _process_appointment(self, text):
        """
        Store one complete source-derived appointment/responsibility
        record in the appropriate section.

        No dates, titles, institutions, or durations are inferred
        or separated from the original source text.
        """

        if self.section == "present":
            self.present_appointments.append(text)

        elif self.section == "past":
            self.past_appointments.append(text)


def fetch_responsibilities_html(url: str) -> str:
    """
    Fetch one faculty member's Responsibilities page.
    """

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def extract_responsibilities(
    html: str,
    faculty_name: str = "",
) -> FacultyResponsibilitiesData:
    """
    Extract structured Responsibilities data from HTML.
    """

    parser = _ResponsibilitiesParser()

    parser.feed(html)
    parser.close()

    return FacultyResponsibilitiesData(
        faculty_name=(
            parser.faculty_name.strip()
            or faculty_name.strip()
        ),
        present_appointments=parser.present_appointments,
        past_appointments=parser.past_appointments,
    )


def extract_responsibilities_from_url(
    faculty_name: str,
    responsibilities_url: str,
) -> FacultyResponsibilitiesData:
    """
    Fetch and extract one faculty member's Responsibilities.
    """

    html = fetch_responsibilities_html(
        responsibilities_url
    )

    return extract_responsibilities(
        html=html,
        faculty_name=faculty_name,
    )


def _print_result(result: FacultyResponsibilitiesData):
    print(f"Faculty: {result.faculty_name}")

    print("\nPresent Appointments:")
    for item in result.present_appointments:
        print(f"  - {item}")

    print("\nPast Appointments:")
    for item in result.past_appointments:
        print(f"  - {item}")


if __name__ == "__main__":
    FACULTY_NAME = "Prof. M.M.Gore"

    RESPONSIBILITIES_URL = (
        "https://mnnit.ac.in/profile/"
        "previewr.php?id=1536"
    )

    result = extract_responsibilities_from_url(
        faculty_name=FACULTY_NAME,
        responsibilities_url=RESPONSIBILITIES_URL,
    )

    _print_result(result)