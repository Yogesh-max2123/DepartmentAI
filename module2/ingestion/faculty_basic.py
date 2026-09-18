from dataclasses import dataclass, field
from html.parser import HTMLParser
import re

import requests


@dataclass
class FacultyBasicData:
    """
    Structured data extracted from one faculty member's
    Basic Information page.
    """

    faculty_name: str = ""
    designation: str = ""
    department: str = ""
    institution: str = ""
    email: str = ""
    telephone: str = ""

    current_courses: list[dict] = field(default_factory=list)
    past_courses: list[dict] = field(default_factory=list)

    education: list[dict] = field(default_factory=list)
    research_areas: list[str] = field(default_factory=list)
    memberships: list[str] = field(default_factory=list)
    research_ids: list[dict] = field(default_factory=list)


class _BasicProfileParser(HTMLParser):
    """
    Parser for the actual MNNIT Basic Information page structure.
    """

    DESIGNATIONS = {
        "professor",
        "associate professor",
        "assistant professor",
        "emeritus professor",
    }

    RESEARCH_ID_TYPES = {
        "ORCID ID:-": "ORCID",
        "Scopus Scholar ID:-": "Scopus Scholar",
        "Google Scholar ID:-": "Google Scholar",
        "Researcher ID:-": "Researcher",
        "Vidawan ID:-": "Vidawan",
    }

    # Examples observed in MNNIT source:
    # CS21324
    # EC22351
    # CSN52103
    #
    # This deliberately requires digits so that strings such as
    # (PPS), (DS), and (DS Lab) are not treated as course codes.
    COURSE_CODE_PATTERN = re.compile(
        r"\(([A-Za-z]{1,8}\d{2,})\)"
    )

    def __init__(self):
        super().__init__()

        # --------------------------------------------------------------
        # Main profile information
        # --------------------------------------------------------------
        self.faculty_name = ""
        self.header_lines = []

        self.designation = ""
        self.department = ""
        self.institution = ""
        self.email = ""
        self.telephone = ""
        # --------------------------------------------------------------
        # Extracted Basic Information data
        # --------------------------------------------------------------
        self.current_courses = []
        self.past_courses = []
        self.education = []
        self.research_areas = []
        self.memberships = []
        self.research_ids = []

        # --------------------------------------------------------------
        # Current parser section
        # --------------------------------------------------------------
        self.section = ""

        # --------------------------------------------------------------
        # <dt> content
        # --------------------------------------------------------------
        self.current_dt_text = ""
        self.current_label = ""

        # --------------------------------------------------------------
        # <dd> content
        # --------------------------------------------------------------
        self.current_dd_parts = []

        # --------------------------------------------------------------
        # Research ID <b> + <a>
        # --------------------------------------------------------------
        self.current_b_parts = []
        self.current_anchor_text = []
        self.current_anchor_href = ""
        self.current_research_id_label = ""

        # --------------------------------------------------------------
        # HTML state
        # --------------------------------------------------------------
        self.in_h1 = False
        self.in_h2 = False
        self.in_header = False
        self.in_dt = False
        self.in_dd = False
        self.in_b = False
        self.in_a = False

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = dict(attrs)

        if tag == "h1":
            self.in_h1 = True

        elif tag == "h2":
            self.in_h2 = True
            self.current_dt_text = ""

        elif tag == "div" and attributes.get("id") == "image":
            self.in_header = True

        elif tag == "dt":
            self.in_dt = True
            self.current_dt_text = ""

        elif tag == "dd":
            self.in_dd = True
            self.current_dd_parts = []

        elif tag == "b":
            self.in_b = True
            self.current_b_parts = []

        elif tag == "a":
            self.in_a = True
            self.current_anchor_text = []
            self.current_anchor_href = attributes.get(
                "href",
                "",
            ).strip()

    def handle_data(self, data):
        text = " ".join(data.split())

        if not text:
            return

        if self.in_h1:
            self.faculty_name = (
                f"{self.faculty_name} {text}".strip()
            )

        if self.in_h2:
            self.current_dt_text = (
                f"{self.current_dt_text} {text}".strip()
            )

        if self.in_header:
            self.header_lines.append(text)

        if self.in_dt:
            self.current_dt_text = (
                f"{self.current_dt_text} {text}".strip()
            )

        if self.in_dd:
            self.current_dd_parts.append(text)

        if self.in_b:
            self.current_b_parts.append(text)

        if self.in_a:
            self.current_anchor_text.append(text)

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
                self.current_dt_text.split()
            )

            self._set_section(heading)
            self.current_dt_text = ""

        elif tag == "dt":
            self.in_dt = False

            label = " ".join(
                self.current_dt_text.split()
            )

            if label:
                self.current_label = label

            self.current_dt_text = ""

        elif tag == "dd":
            self.in_dd = False

            text = " ".join(
                self.current_dd_parts
            ).strip()

            if text:
                self._process_dd(text)

            self.current_dd_parts = []

        elif tag == "b":
            self.in_b = False

            label = " ".join(
                self.current_b_parts
            ).strip()

            if self.section == "research_ids" and label:
                self.current_research_id_label = label

            self.current_b_parts = []

        elif tag == "a":
            self.in_a = False

            if (
                self.section == "research_ids"
                and self.current_anchor_text
            ):
                value = " ".join(
                    self.current_anchor_text
                ).strip()

                self._process_research_id(
                    value=value,
                    href=self.current_anchor_href,
                    label=self.current_research_id_label,
                )

            self.current_anchor_text = []
            self.current_anchor_href = ""

    # ------------------------------------------------------------------
    # Section handling
    # ------------------------------------------------------------------

    def _set_section(self, heading):
        heading = " ".join(
            heading.split()
        ).strip().lower()

        if heading == "teaching":
            self.section = "teaching"

        elif heading == "education":
            self.section = "education"

        elif heading == "areas of research":
            self.section = "research_areas"

        elif heading == "professional membership":
            self.section = "memberships"

        elif heading == "research id's":
            self.section = "research_ids"

        else:
            self.section = ""

        self.current_label = ""
        self.current_research_id_label = ""

    # ------------------------------------------------------------------
    # Header extraction
    # ------------------------------------------------------------------

    def extract_header_data(self):
        """
        Extract designation, department, institution, email and
        telephone from the text lines inside <div id="image">.
        """

        lines = [
            " ".join(line.split()).strip()
            for line in self.header_lines
            if line.strip()
        ]

        for index, line in enumerate(lines):
            lowered = line.lower()

            if lowered.startswith("e-mail:"):
                self.email = line[len("E-mail:"):].strip()

            elif lowered.startswith("telephone:"):
                self.telephone = line[len("Telephone:"):].strip()

            elif lowered in self.DESIGNATIONS:
                self.designation = line

            elif lowered.startswith("department"):
                self.department = line

                if index + 1 < len(lines):
                    next_line = lines[index + 1]

                    if (
                        "institute" in next_line.lower()
                        or "university" in next_line.lower()
                    ):
                        self.institution = next_line

        # Fallback institution detection.
        if not self.institution:
            for line in lines:
                lowered = line.lower()

                if (
                    "national institute" in lowered
                    or "institute" in lowered
                    or "university" in lowered
                ):
                    if not lowered.startswith("department"):
                        self.institution = line
                        break

    # ------------------------------------------------------------------
    # Section data extraction
    # ------------------------------------------------------------------

    def _process_dd(self, text):
        if self.section == "teaching":
            self._process_course_record(text)

        elif self.section == "education":
            self.education.append(
                {
                    "level": self.current_label.rstrip(":").strip(),
                    "details": text,
                }
            )

        elif self.section == "research_areas":
            self.research_areas.append(text)

        elif self.section == "memberships":
            self.memberships.append(text)

    def _process_course_record(self, text):
        """
        Process one course DD record.

        Explicit course codes are extracted individually. The text
        between one explicit course code and the next is retained as
        the corresponding course name.

        Important:
        - Only codes matching COURSE_CODE_PATTERN are treated as
          course codes.
        - Source text such as '(PPS)' and '(DS)' remains part of the
          course name.
        - '&' remains part of the source-derived course name.
        - No course information is invented.
        """

        label = self.current_label.lower()

        if label.startswith("current courses"):
            target = self.current_courses

        elif label.startswith("past courses"):
            target = self.past_courses

        else:
            return

        target.extend(
            self._parse_course_text(text)
        )

    @classmethod
    def _parse_course_text(cls, text):
        """
        Parse explicitly coded courses from one source DD record.

        The MNNIT source uses both formats:

            (CS21324) Secure E-Commerce

        and:

            E-Commerce (CS35102)

        It also contains paired records such as:

            (CS31101) Programming and Problem Solving (PPS)
            & (CS31201) PPS Lab

        Only explicit course-code patterns are treated as course
        codes. Parenthesized abbreviations such as (PPS) and (DS)
        are preserved as normal source text.

        No course information is invented.
        """

        matches = list(
            cls.COURSE_CODE_PATTERN.finditer(text)
        )

        # No explicit course code.
        if not matches:
            return [
                {
                    "course_code": "",
                    "course_name": text,
                    "raw_text": text,
                }
            ]

        courses = []

        for index, match in enumerate(matches):
            course_code = match.group(1).strip()

            # ----------------------------------------------------------
            # Determine the text boundaries for this course.
            # ----------------------------------------------------------
            previous_end = (
                matches[index - 1].end()
                if index > 0
                else 0
            )

            current_start = match.start()

            next_start = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )

            # Text immediately associated with this code.
            before_code = text[
                previous_end:current_start
            ].strip()

            after_code = text[
                match.end():next_start
            ].strip()

            # ----------------------------------------------------------
            # Case 1:
            # Course name appears before the code.
            #
            # Example:
            #     E-Commerce (CS35102)
            #
            # For the first code in a record, the text before the code
            # is the course name.
            # ----------------------------------------------------------
            if index == 0 and before_code:
                course_name = before_code

            # ----------------------------------------------------------
            # Case 2:
            # Normal format:
            #
            #     (CS21324) Secure E-Commerce
            #
            # or a subsequent course:
            #
            #     ... (CS31201) PPS Lab
            # ----------------------------------------------------------
            else:
                course_name = after_code

            # ----------------------------------------------------------
            # For a paired record, preserve the '&' at the end of the
            # previous course name exactly as it appears in the source.
            #
            # Example:
            #
            #     (CS31101) Programming and Problem Solving (PPS) &
            #     (CS31201) PPS Lab
            #
            # becomes:
            #
            #     CS31101 | Programming and Problem Solving (PPS) &
            #     CS31201 | PPS Lab
            # ----------------------------------------------------------
            if index > 0 and before_code:
                if before_code.endswith("&"):
                    course_name = after_code

            # ----------------------------------------------------------
            # If a course uses the "name before code" format, there may
            # be no text after the code. Keep the name already extracted.
            # ----------------------------------------------------------
            course_name = course_name.strip()

            # Preserve the exact source text associated with this code.
            if index == 0:
                if before_code:
                    raw_text = text[
                        current_start - len(before_code):
                        next_start
                    ].strip()
                else:
                    raw_text = text[
                        match.start():
                        next_start
                    ].strip()
            else:
                raw_text = text[
                    match.start():
                    next_start
                ].strip()

            courses.append(
                {
                    "course_code": course_code,
                    "course_name": course_name,
                    "raw_text": raw_text,
                }
            )

        return courses
    def _process_research_id(
        self,
        value,
        href,
        label,
    ):
        """
        Extract Research ID records.

        The MNNIT source provides:
            <b>ORCID ID:-</b>
            <a href="...">0000-...</a>
        """

        normalized_label = (
            label.strip()
            if label
            else ""
        )

        id_type = self.RESEARCH_ID_TYPES.get(
            normalized_label,
            "",
        )

        # Fallback based on link destination if the source label
        # differs slightly on another faculty page.
        if not id_type:
            href_lower = href.lower()

            if "orcid.org" in href_lower:
                id_type = "ORCID"

            elif "scopus.com" in href_lower:
                id_type = "Scopus Scholar"

            elif "scholar.google" in href_lower:
                id_type = "Google Scholar"

            elif "researcherid.com" in href_lower:
                id_type = "Researcher"

            elif "mnnit.irins.org" in href_lower:
                id_type = "Vidawan"

        if not value:
            return

        self.research_ids.append(
            {
                "type": (
                    id_type
                    or normalized_label.rstrip(":-").strip()
                ),
                "value": value,
                "url": href,
            }
        )


def fetch_basic_profile_html(url: str) -> str:
    """
    Fetch one faculty member's Basic Information page.
    """

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def extract_basic_profile(
    html: str,
    faculty_name: str = "",
) -> FacultyBasicData:
    """
    Extract structured Basic Information data from HTML.
    """

    parser = _BasicProfileParser()

    parser.feed(html)
    parser.close()

    parser.extract_header_data()

    return FacultyBasicData(
        faculty_name=(
            parser.faculty_name.strip()
            or faculty_name.strip()
        ),
        designation=parser.designation.strip(),
        department=parser.department.strip(),
        institution=parser.institution.strip(),
        email=parser.email.strip(),
        telephone=parser.telephone.strip(),
        current_courses=parser.current_courses,
        past_courses=parser.past_courses,
        education=parser.education,
        research_areas=parser.research_areas,
        memberships=parser.memberships,
        research_ids=parser.research_ids,
    )


def extract_basic_profile_from_url(
    faculty_name: str,
    basic_url: str,
) -> FacultyBasicData:
    """
    Fetch and extract one faculty member's Basic Information.
    """

    html = fetch_basic_profile_html(basic_url)

    return extract_basic_profile(
        html=html,
        faculty_name=faculty_name,
    )


def _print_result(result: FacultyBasicData):
    print(f"Faculty: {result.faculty_name}")
    print(f"Designation: {result.designation}")
    print(f"Department: {result.department}")
    print(f"Institution: {result.institution}")
    print(f"Email: {result.email}")
    print(f"Telephone: {result.telephone}")

    print("\nCurrent Courses:")
    for course in result.current_courses:
        print(
            f"  - {course['course_code']} | "
            f"{course['course_name']}"
        )

    print("\nPast Courses:")
    for course in result.past_courses:
        print(
            f"  - {course['course_code']} | "
            f"{course['course_name']}"
        )

    print("\nEducation:")
    for item in result.education:
        print(
            f"  - {item['level']}: "
            f"{item['details']}"
        )

    print("\nResearch Areas:")
    for item in result.research_areas:
        print(f"  - {item}")

    print("\nProfessional Memberships:")
    for item in result.memberships:
        print(f"  - {item}")

    print("\nResearch IDs:")
    for item in result.research_ids:
        print(
            f"  - {item['type']}: "
            f"{item['value']}"
        )

        if item["url"]:
            print(f"    URL: {item['url']}")


if __name__ == "__main__":
    FACULTY_NAME = "Prof. M.M.Gore"
    BASIC_URL = (
        "https://mnnit.ac.in/profile/"
        "preview.php?login=gore"
    )

    result = extract_basic_profile_from_url(
        faculty_name=FACULTY_NAME,
        basic_url=BASIC_URL,
    )

    _print_result(result)
