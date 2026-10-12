"""Synthetic tests for the reference code. Run: python -m pytest reference -q  (no real data used)."""
import pytest
from packed_parser import *

HDR = "Student: Party ID|Student: First Name|Program: Code|Student: Start Date"

def test_is_packed_detects_pipe_header():
    rows = [[HDR + "|a|b|c|d|e|f|g"]] + [["0000012345|Ann|BSB50|1/1/2025|||||||"]] * 5
    assert is_packed(rows)

def test_is_packed_false_for_real_table():
    rows = [["id", "name"], ["1", "x"]]
    assert not is_packed(rows)

def test_comma_split_rows_are_rejoined():
    # Excel split "Identify fibres, fabrics and textiles" into two cells
    header = [HDR]
    rows = [header,
            ["0000012345|Ann|BSB50|1/1/2025"],
            ["0000012346|Identify fibres", " fabrics and textiles|BSB50|1/1/2025"]]
    h, rec, q, st = parse_packed(rows)
    assert st["parsed_rows"] == 2 and st["repaired_rows"] == 1 and st["quarantined_rows"] == 0
    assert rec[1][1][1] == "Identify fibres, fabrics and textiles"

def test_wrong_field_count_is_quarantined():
    rows = [[HDR], ["0000012345|Ann|BSB50"]]
    h, rec, q, st = parse_packed(rows)
    assert st["quarantined_rows"] == 1 and st["parsed_rows"] == 0

def test_quoted_empty_values():
    rows = [[HDR], ['0000012345|""|BSB50|1/1/2025']]
    h, rec, q, st = parse_packed(rows)
    assert rec[0][1][1] == ""

def test_fingerprint_types():
    assert classify_report(FINGERPRINTS["MOODLE"]) == "MOODLE"
    with pytest.raises(ValueError):
        classify_report(["a", "b"])

@pytest.mark.parametrize("name,college", [
    ("Report_Overall_Student_Profile_AIBT.xlsx", "AIBT"),
    ("Report_Overall_Student_Profile_AIBTI.xlsx", "AIBTI"),
    ("AC_Unit_outcomes_report-NPA-20261102.xlsx", "NPA"),
    ("progression_hji.xlsx", "HJI"),
])
def test_college_from_filename(name, college):
    assert college_from_filename(name) == college

def test_filename_without_or_with_two_colleges_fails():
    for bad in ("report.xlsx", "report_AIBT_NPA.xlsx"):
        with pytest.raises(ValueError):
            college_from_filename(bad)

@pytest.mark.parametrize("raw,expected", [
    ("0000013732", ("OK", "AIBT", "13732")),
    ("0000005506", ("OK", "AIBT", "5506")),
    ("NP00012345", ("OK", "NPA", "12345")),
    ("AV00000007", ("OK", "AVTA", "7")),
    ("AI00012345", ("OK", "AIBTI", "12345")),
    ("RC00012345", ("OK", "RCC", "12345")),
    ("HJ00012345", ("OK", "HJI", "12345")),
    ("STAFF01", ("EXCLUDED", None, None)),
    ("test99", ("EXCLUDED", None, None)),
    ("ABC123", ("UNASSIGNED", None, None)),
    ("0000000000", ("UNASSIGNED", None, None)),
    ("13732.0", ("UNASSIGNED", None, None)),
])
def test_resolve_id(raw, expected):
    assert resolve_id(raw) == expected

def test_moodle_core():
    assert moodle_core(13732) == "13732"
    assert moodle_core("13732.0") == "13732"
    assert moodle_core(0) is None

def test_unit_and_date_normalization():
    assert norm_unit(" bsbfin-601 ") == "BSBFIN601"
    assert norm_unit("") is None
    assert parse_date("28/2/0206") is None
    assert parse_date("15/03/2026").year == 2026

def test_sms_outcome_blank_is_not_failure():
    assert sms_outcome_class("") == "BLANK"
    assert sms_outcome_class("Credit transfer/national recognition") == "SUCCESS"
    assert sms_outcome_class("Not Competent") == "OTHER"
