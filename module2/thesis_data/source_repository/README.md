# DepartmentAI Module II — Thesis Source Data

This package organizes the supplied `THESIS SUPERVISED FACULTY CSED.txt` into faculty-wise plain-text files.

## Contents
- `faculty/`: one source-preserving text file per faculty section with numbered rows detected.
- `faculty_index.csv`: faculty names, filenames, source line ranges, and a rough numbered-row count for navigation only.
- `source_original/THESIS SUPERVISED FACULTY CSED.txt`: original input file preserved as supplied.

## Important data-handling rules
- These files preserve the supplied source text. They are not a normalized database import.
- Do not infer programme, status, registration year, or completion year where the source does not explicitly establish it.
- The index row count is a simple navigation aid, not a validated count of unique thesis records.
- We will use these files as the source-of-truth working set for later per-faculty validation and database reconciliation.
- No database, retrieval code, or application files are changed by this package.
