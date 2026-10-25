"""
Safely repair Dr. Mayank Pandey's thesis-supervision rows in Module II.

Source basis: the user-provided official-profile table (51 rows).
This script updates existing matching rows only. It does not delete rows.
It validates all 51 matches before making any database changes and rolls back
if a row is missing or ambiguous.

Run from the DepartmentAI project root:
    python -m module2.ingestion.repair_mayank_thesis_data
"""

import re
import sys
from difflib import SequenceMatcher

from module2.database.connection import get_connection

FACULTY_NAME = "Mayank Pandey"

# (program_level, status, student_name, research_topic, source_year, year_kind)
# year_kind is "completion" for completed Ph.D./M.Tech. entries and
# "registration" for ongoing Ph.D. entries.
SOURCE_ROWS = [('Ph.D.',
  'Completed',
  'Shashwati Banerjea',
  'Design & Implementation of Computation-as-a-Service Infrastructure over P2P Cloud of Underutilized '
  'Resources',
  2017,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Debjani Ghosh',
  'Formal Modelling & Verification of Peer-to-Peer Video-on-Demand Streaming',
  2018,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Abha Trivedi',
  'Agent Based Modelling to simulate crowd management & control strategies in religious crowd gathering',
  2020,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Krishna Vijay Kumar Singh',
  'Design and Implementation of SDN Framework for Mobility in WiFi Networks',
  2020,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Anurag Sewak',
  'Design and Implementation of Opportunistic Overlay and Underlay for P2P File Sharing among Mobile Nodes '
  'in IEEE 802.11 Networks',
  2020,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Shabir Ali',
  'Design and Implementation of Software Defined Communication and Computation Infrastructure for '
  'Semi-permanent Smart Environments.',
  2021,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Nitin Shukla',
  'Design and Implementation of Software Defined Low Overhead Structured Peer-to-peer Networks.',
  2021,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Akhilesh Kumar',
  'Design and Implementation of a Software- Defined Churn Tolerant Peer-to-Peer Content Delivery Network at '
  'the Edge for Adaptive Video Streaming',
  2024,
  'completion'),
 ('Ph.D.',
  'Completed',
  'Dharmendra Kumar',
  'Design of Efficient Data Sharing System for a Peer-to-Peer Network',
  2023,
  'completion'),
 ('Ph.D.',
  'Ongoing',
  'Amit Kumar Singh',
  'Inband Network Telemetry Using Data Plane Programmability',
  2021,
  'registration'),
 ('Ph.D.',
  'Ongoing',
  'Akhildev Mishra',
  'Design and Implementation of an Intelligent, Latency-Aware UPF Orchestration Framework for MEC-Integrated '
  '5G Core Networks',
  2025,
  'registration'),
 ('M.Tech',
  'Completed',
  'Ajit C. Awekar',
  'Quality of Service Parameters for Publish/Subscribe Based Mobile Ad-hoc Networks',
  2008,
  'completion'),
 ('M.Tech',
  'Completed',
  'Dharmendra Kumar',
  'Performance Comparison of Ad-hoc Routing Protocols (AODV, DSR and DSDV) in MANET using Network Simulator',
  2008,
  'completion'),
 ('M.Tech',
  'Completed',
  'Rupesh Kumar',
  'Notification Ferrying in Vehicular Ad-hoc Network using Publish/Subscribe Communication Architecture',
  2008,
  'completion'),
 ('M.Tech', 'Completed', 'Vivek Srivastava', 'Analysis of QOS for AODV Protocol', 2008, 'completion'),
 ('M.Tech',
  'Completed',
  'Sonam Pahariya',
  'Enabling Security in Content based Publish/Subscribe P2P Network using Proxy Re-Encryption',
  2009,
  'completion'),
 ('M.Tech',
  'Completed',
  'Jagriti Jadoun',
  'Super-Peer Selection Strategy Based on Trust and Reputation in Multi-tier Structured Overlay',
  2009,
  'completion'),
 ('M.Tech', 'Completed', 'Debjani Ghosh', 'Modeling Priority in Publish/Subscribe', 2009, 'completion'),
 ('M.Tech',
  'Completed',
  'Akhilesh Kumar',
  'Techniques for Forming P2P connection across HTTP Proxies',
  2010,
  'completion'),
 ('M.Tech',
  'Completed',
  'Saroj Kumar Behera',
  'Developing Automation Testing Framework for Citrix Xen App Application Streaming Project',
  2010,
  'completion'),
 ('M.Tech',
  'Completed',
  'Varun Kumar Pathak',
  'Design and Implementation of Content Dissemination with Semantic Support over Structured P2P Overlay',
  2011,
  'completion'),
 ('M.Tech',
  'Completed',
  'Shiraj Pokharel',
  'Simulation Based Analysis of Semantically Evolving Structured P2P Overlay',
  2011,
  'completion'),
 ('M.Tech',
  'Completed',
  'Jayati Kesarwani',
  'Proactive Tunig of Ring Sizes in Hierarchical Multi-ring Structured P2P Overlay',
  2011,
  'completion'),
 ('M.Tech',
  'Completed',
  'Anurag Sewak',
  'WebChord - A Web-based Implementation of Chord P2P Lookup Service',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Sagar Pareek',
  'Developing of Simulation Platform for P2P over VANET',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Shraddha Dixit',
  'Design and Implementation of metadata Editor for Digital Educational Content',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Satyendra Sharma',
  'Semantic Chunking Based P2P Video-Streaming of NPTEL Video courses in LAN Environment',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Rohit Kumar Gupta',
  'Design and Implementation of P2P Video-Streaming Across Different Private Networks',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Vipin Kumar Pandey',
  'Implementing Evolution of Internet Based P2P Communities',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Alok Kumar Kashyap',
  'Property Based Testing of Hierarchical DHT Design Using Erlang',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Shashank Gupta',
  'Ontology based Matching Engine for Publish/Subscribe',
  2012,
  'completion'),
 ('M.Tech',
  'Completed',
  'Punit Kumar Chaubey',
  'Analysis of Applying Trust and Reputation Management Algorithms for Content Sharing in Hierarchical DHT '
  'Overlays.',
  2013,
  'completion'),
 ('M.Tech',
  'Completed',
  'Ajay Kumar Das',
  'Implementation of Mobile Agent to Assist Trusted Role Changing in hierarchical DHT Overlays.',
  2013,
  'completion'),
 ('M.Tech',
  'Completed',
  'Anju Pandey',
  'Modelling Stochastic Aspects of Publish/Subscribe Communication Paradigm using Performance Evaluation '
  'Process Algebra.',
  2013,
  'completion'),
 ('M.Tech',
  'Completed',
  'Sandeep Pandey',
  'Implementation of Data Structure Visualization Tool.',
  2013,
  'completion'),
 ('M.Tech',
  'Completed',
  'Akhilesh Kumar Singh',
  'Simulative Analysis of Popular Structured and Unstructured P2P Overlays.',
  2013,
  'completion'),
 ('M.Tech',
  'Completed',
  'Shailender Kumar Singh',
  'Implementation of Mobile IP Test-Bed.',
  2013,
  'completion'),
 ('M.Tech', 'Completed', 'Naveen Kumar', 'Simulation of Publish-Subscribe over DHT.', 2014, 'completion'),
 ('M.Tech',
  'Completed',
  'Nitin Shukla',
  'Stochastic Analysis of Event Based System Using Performance Evaluation Process Algebra.',
  2014,
  'completion'),
 ('M.Tech',
  'Completed',
  'Moni Chandel',
  'Implementation of Focus UI Feature in Toolbar Control on Tizen Platform.',
  2014,
  'completion'),
 ('M.Tech',
  'Completed',
  'Rahul Kumar Soni',
  'Performance Evaluation of TCP Variants Over Proactive and Reactive Routing Protocols in Mobile Adhoc '
  'Networks',
  2015,
  'completion'),
 ('M.Tech',
  'Completed',
  'Misha Hungyo',
  'An Implementation of Topic- Based Publish-Subscribe Paradigm Using SDN.',
  2015,
  'completion'),
 ('M.Tech',
  'Completed',
  'Chanchal Talreja',
  'Ontology Based Publish/Subscribe Using Software Defined Networking.',
  2016,
  'completion'),
 ('M.Tech',
  'Completed',
  'Gopal Chandra Tudu',
  'Application Based Network Slicing Using Flow Visor in Software Defined Networking',
  2016,
  'completion'),
 ('M.Tech',
  'Completed',
  'Anurag Bamal',
  'SDN-Enabled Location Aware Optimized Structured P2P Overlay.',
  2017,
  'completion'),
 ('M.Tech', 'Completed', 'Rishabh Jain', 'SDN-Based Dynamic Video Streaming Using DASH.', 2018, 'completion'),
 ('M.Tech',
  'Completed',
  'Deepmalya Dutta',
  'SDN-Enabled Location Aware Optimized Low Maintenance Overhead P2P Overlay.',
  2018,
  'completion'),
 ('M.Tech',
  'Completed',
  'Vishesh Bajpai',
  'Design and Implementation of Hardware Diagnostic Utility for Tegra Display.',
  2019,
  'completion'),
 ('M.Tech',
  'Completed',
  'Omesh Sudhakar',
  'Improving Performance and Lifetime of SSDs using Hardware Compression.',
  2019,
  'completion'),
 ('M.Tech',
  'Completed',
  'Nitin Kumar Yadav',
  'Secure Key Configuration for Storage Devices and Boot KPI Automation.',
  2019,
  'completion'),
 ('M.Tech',
  'Completed',
  'Komal Agarwal',
  'Offloading of Storage Efficiency Operation in ONTAP',
  2019,
  'completion')]


def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def topic_similarity(left, right):
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def main():
    if len(SOURCE_ROWS) != 51:
        raise RuntimeError(f"Expected 51 source rows, found {len(SOURCE_ROWS)}.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT f.id, COUNT(ts.id) AS thesis_rows
                FROM m2_faculties f
                LEFT JOIN m2_thesis_supervision ts ON ts.faculty_id = f.id
                WHERE BTRIM(f.full_name) ILIKE %s
                GROUP BY f.id
                ORDER BY COUNT(ts.id) DESC, f.id
                """,
                (f"%{FACULTY_NAME}" ,),
            )
            faculty_matches = cur.fetchall()
            faculty_ids_with_rows = [row[0] for row in faculty_matches if row[1] > 0]

            if len(faculty_ids_with_rows) != 1:
                raise RuntimeError(
                    "Safety check failed: expected exactly one faculty_id with existing "
                    f"thesis rows for {FACULTY_NAME!r}; found {faculty_ids_with_rows}. "
                    "No changes were made."
                )
            faculty_id = faculty_ids_with_rows[0]

            cur.execute(
                """
                SELECT id, student_name, research_topic, program_level,
                       registration_year, completion_year, status
                FROM m2_thesis_supervision
                WHERE faculty_id = %s
                ORDER BY id
                """,
                (faculty_id,),
            )
            existing = cur.fetchall()

            if len(existing) != 51:
                raise RuntimeError(
                    "Safety check failed: expected 51 existing thesis rows for "
                    f"Mayank Pandey, found {len(existing)}. No changes were made."
                )

            existing_records = []
            for row in existing:
                existing_records.append({
                    "id": row[0],
                    "student_name": row[1],
                    "research_topic": row[2],
                    "program_level": row[3],
                    "registration_year": row[4],
                    "completion_year": row[5],
                    "status": row[6],
                })

            used_ids = set()
            updates = []
            unresolved = []

            def name_matches(source_name, stored_name):
                source_norm = normalize(source_name)
                stored_norm = normalize(stored_name)
                # Permit source annotations stored after a student's name, e.g.
                # "Amit Kumar Singh (State-of-the-art done)", but not arbitrary
                # partial-name matches.
                return (
                    stored_norm == source_norm
                    or stored_norm.startswith(source_norm + " ")
                )

            # Match by normalized student name; when names repeat or carry
            # annotations, disambiguate using research-topic similarity.
            for program, status, student, topic, year, year_kind in SOURCE_ROWS:
                candidates = [
                    candidate for candidate in existing_records
                    if candidate["id"] not in used_ids
                    and name_matches(student, candidate["student_name"])
                ]

                ranked = sorted(
                    ((topic_similarity(topic, c["research_topic"]), c) for c in candidates),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                if len(ranked) == 1:
                    score, chosen = ranked[0]
                    # A blank or substantially different topic must not be silently
                    # accepted, even when the student name is unique.
                    if chosen["research_topic"] and score < 0.40:
                        unresolved.append(
                            f"Topic mismatch for student {student!r}: stored row id={chosen['id']}, "
                            f"stored topic={chosen['research_topic']!r}, similarity={score:.3f}; "
                            f"source topic={topic!r}."
                        )
                        continue
                elif len(ranked) > 1:
                    best_score, best = ranked[0]
                    second_score, second = ranked[1]
                    if best_score < 0.40 or (best_score - second_score) < 0.05:
                        unresolved.append(
                            f"Ambiguous match for {student!r} / {topic!r}; candidates="
                            f"{[(round(score, 3), c['id'], c['student_name'], c['research_topic']) for score, c in ranked[:5]]}"
                        )
                        continue
                    chosen = best
                else:
                    # Include likely rows in the diagnostic so the next fix can
                    # be evidence-based rather than weakening validation.
                    likely = sorted(
                        (
                            (
                                SequenceMatcher(
                                    None, normalize(student), normalize(c["student_name"])
                                ).ratio(),
                                topic_similarity(topic, c["research_topic"]),
                                c,
                            )
                            for c in existing_records if c["id"] not in used_ids
                        ),
                        key=lambda item: (item[0], item[1]),
                        reverse=True,
                    )[:5]
                    unresolved.append(
                        f"No safe match for source student {student!r} / topic {topic!r}. "
                        f"Closest stored rows (name_score, topic_score, id, stored_name, stored_topic)="
                        f"{[(round(ns, 3), round(ts, 3), c['id'], c['student_name'], c['research_topic']) for ns, ts, c in likely]}"
                    )
                    continue

                used_ids.add(chosen["id"])
                registration_year = year if year_kind == "registration" else None
                completion_year = year if year_kind == "completion" else None
                updates.append((
                    program, status, student, topic,
                    registration_year, completion_year, chosen["id"],
                ))

            if unresolved or len(updates) != 51 or len(used_ids) != 51:
                raise RuntimeError(
                    "Safety validation failed; no rows were updated.\n- "
                    + "\n- ".join(unresolved or [
                        f"Matched {len(updates)} of 51 source rows."
                    ])
                )

            for update in updates:
                cur.execute(
                    """
                    UPDATE m2_thesis_supervision
                    SET program_level = %s,
                        status = %s,
                        student_name = %s,
                        research_topic = %s,
                        registration_year = %s,
                        completion_year = %s
                    WHERE id = %s AND faculty_id = %s
                    """,
                    update[:-1] + (update[-1], faculty_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Expected to update exactly one row with id={update[-1]}, "
                        f"updated {cur.rowcount}. Transaction will roll back."
                    )

            # Verify key expected totals before commit.
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE program_level ILIKE '%%ph%%d%%') AS phd_total,
                    COUNT(*) FILTER (
                        WHERE program_level ILIKE '%%ph%%d%%' AND status = 'Completed'
                    ) AS phd_completed,
                    COUNT(*) FILTER (
                        WHERE program_level ILIKE '%%ph%%d%%' AND status = 'Ongoing'
                    ) AS phd_ongoing,
                    COUNT(*) FILTER (WHERE program_level ILIKE '%%m.tech%%') AS mtech_total,
                    COUNT(*) FILTER (
                        WHERE completion_year BETWEEN 2020 AND 2025
                    ) AS completed_2020_2025,
                    COUNT(*) FILTER (
                        WHERE registration_year BETWEEN 2020 AND 2025
                    ) AS registered_2020_2025,
                    COUNT(*) FILTER (
                        WHERE (registration_year BETWEEN 2020 AND 2025)
                           OR (completion_year BETWEEN 2020 AND 2025)
                    ) AS any_year_2020_2025,
                    COUNT(*) FILTER (
                        WHERE registration_year IS NULL AND completion_year IS NULL
                    ) AS missing_both_years
                FROM m2_thesis_supervision
                WHERE faculty_id = %s
                """,
                (faculty_id,),
            )
            totals = cur.fetchone()
            expected = (51, 11, 9, 2, 40, 7, 2, 9, 0)
            if tuple(totals) != expected:
                raise RuntimeError(
                    f"Post-update verification failed: got {tuple(totals)}, "
                    f"expected {expected}. Transaction will roll back."
                )

        conn.commit()

    print("Repair completed successfully for Dr. Mayank Pandey.")
    print("Updated existing rows: 51 (no rows deleted or inserted).")
    print("Ph.D. records: 11 (9 completed, 2 ongoing).")
    print("M.Tech records: 40.")
    print("Records with listed registration OR completion year from 2020 through 2025: 9.")
    print("Completed records from 2020 through 2025: 7.")
    print("Records missing both year fields: 0.")
    print("Existing source_url and details fields were preserved.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Keep expected validation/database failures readable in PowerShell.
        # Do not hide the error reason, but avoid a long traceback by default.
        print(f"ERROR: {exc}", file=sys.stderr)
        print("No successful repair should be assumed. Review the diagnostic above before retrying.", file=sys.stderr)
        sys.exit(1)
