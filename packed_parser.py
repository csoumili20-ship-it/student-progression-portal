"""Reference implementation: packed-delimiter repair, fingerprinting, college resolution,
normalization and duplicate classification for the Student Progression Portal.
Seed for the AI agents. Validated on real AIBT files (see VERIFIED_RESULTS.md)."""
import csv, re
from dataclasses import dataclass

# ---------- 1. Packed-delimiter repair (Profile and Outcomes) ----------
def rows_from_sheet(ws):
    """Yield each sheet row as a list of cell values (trailing empties removed)."""
    for r in ws.iter_rows(values_only=True):
        cells = list(r)
        while cells and cells[-1] is None:
            cells.pop()
        yield cells

def is_packed(rows, sample=200, min_pipes=10, share=0.95):
    """Packed = header is ONE cell holding many pipes AND >=95% of sampled rows have a pipe in cell 0."""
    if not rows:
        return False
    h = rows[0]
    if len(h) != 1 or str(h[0]).count("|") < min_pipes:
        return False
    body = rows[1:1 + sample]
    if not body:
        return False
    ok = sum(1 for r in body if r and "|" in str(r[0]))
    return ok / len(body) >= share

def parse_packed(rows):
    """Rejoin comma-split cells with a comma, split on pipes with CSV quoting.
    Returns (header, records, quarantine, stats)."""
    joined = [",".join("" if c is None else str(c) for c in r) for r in rows]
    header = [h.strip() for h in joined[0].split("|")]
    n = len(header)
    records, quarantine, repaired = [], [], 0
    for i, (cells, line) in enumerate(zip(rows[1:], joined[1:]), start=2):
        if len(cells) > 1:
            repaired += 1
        parts = next(csv.reader([line], delimiter="|", quotechar='"'))
        if len(parts) != n:
            quarantine.append((i, len(parts), line[:200]))
        else:
            records.append((i, parts))
    stats = dict(source_rows=len(rows) - 1, parsed_rows=len(records),
                 repaired_rows=repaired, quarantined_rows=len(quarantine))
    return header, records, quarantine, stats

# ---------- 2. Report fingerprinting ----------
FINGERPRINTS = {
    "PROFILE": {"Student: Party ID", "Program: Code", "Student: Start Date", "Student: Target End Date",
                "Student: Total Units Enrolled", "Student: Total Units Completed", "Student: Enrolment Status"},
    "OUTCOMES": {"Student: Party ID", "Program: Code", "Student: Start Date",
                 "Student Unit Status: Code", "Student Unit Status: Outcome", "Student Unit Status: Start Date"},
    "CERTIFICATE": {"Student: Party ID", "Program: Code", "Certificate Register: Certificate Number",
                    "Certificate Register: Certificate Type", "Student: Qualification Issued"},
    "MOODLE": {"student_rto_id", "unit_code", "course_idnumber", "count_total_assessments",
               "count_satisfactory", "actual_moodle_course_outcome"},
}
def classify_report(columns):
    cols = {c.strip() for c in columns}
    hits = [k for k, req in FINGERPRINTS.items() if req <= cols]
    if len(hits) != 1:
        raise ValueError(f"Report type not recognised or ambiguous: {hits}")
    return hits[0]

# ---------- 3. College resolution ----------
@dataclass(frozen=True)
class IdRule:
    college: str
    pattern: re.Pattern
    prefix_len: int      # letters to strip before leading zeros
    priority: int = 100

DEFAULT_ID_RULES = [
    IdRule("AIBT",  re.compile(r"^00000[0-9]{5}$"), 0),
    IdRule("NPA",   re.compile(r"^NP[0-9]{8}$"), 2),
    IdRule("AVTA",  re.compile(r"^AV[0-9]{8}$"), 2),
    IdRule("AIBTI", re.compile(r"^AI[0-9]{8}$"), 2),
    IdRule("RCC",   re.compile(r"^RC[0-9]{8}$"), 2),
    IdRule("HJI",   re.compile(r"^HJ[0-9]{8}$"), 2),
]
EXCLUSIONS = [re.compile(r"^STAFF", re.I), re.compile(r"^TEST", re.I)]
FILE_TOKENS = {"AIBT": "AIBT", "NPA": "NPA", "AVTA": "AVTA", "AIBTI": "AIBTI", "RCC": "RCC", "HJI": "HJI"}

def college_from_filename(name):
    """Whole-token match: AIBT never matches inside AIBTI."""
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    tokens = {t.upper() for t in re.split(r"[^A-Za-z0-9]+", stem) if t}
    found = {FILE_TOKENS[t] for t in tokens if t in FILE_TOKENS}
    if len(found) != 1:
        raise ValueError(f"Cannot determine a single college from file name {name!r}: {sorted(found)}")
    return found.pop()

def resolve_id(raw, rules=DEFAULT_ID_RULES):
    """Return (status, college, numeric_core). status: OK | EXCLUDED | UNASSIGNED."""
    s = str(raw).strip()
    s = re.sub(r"\.0+$", "", s)
    if any(p.search(s) for p in EXCLUSIONS):
        return "EXCLUDED", None, None
    for r in sorted(rules, key=lambda r: r.priority):
        if r.pattern.match(s):
            core = s[r.prefix_len:].lstrip("0")
            return ("OK", r.college, core) if core else ("UNASSIGNED", None, None)
    return "UNASSIGNED", None, None

def moodle_core(value):
    """Moodle IDs arrive as integers; 0 means an unlinked account."""
    s = re.sub(r"\.0+$", "", str(value).strip())
    digits = re.sub(r"^[A-Za-z]+", "", s).lstrip("0")
    return digits or None

# ---------- 4. Normalization helpers ----------
def norm_unit(v):
    s = re.sub(r"[^A-Za-z0-9]", "", str(v or "")).upper()
    return s or None

def parse_date(v, min_year=2010, max_year=2035):
    from datetime import datetime
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d if min_year <= d.year <= max_year else None
        except ValueError:
            continue
    return None

SMS_SUCCESS = {"competent", "credit transfer/national recognition", "rpl - granted",
               "rcc - granted", "competency achieved via gap"}
def sms_outcome_class(v):
    s = str(v or "").strip().lower()
    if not s:
        return "BLANK"
    return "SUCCESS" if s in SMS_SUCCESS else "OTHER"
