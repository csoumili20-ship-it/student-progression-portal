"""Usage: python verify_on_real_files.py PROFILE.xlsx OUTCOMES.xlsx CERTIFICATE.xlsx MOODLE.xlsx
(Certificate may be .xls converted to .xlsx, or read via a legacy reader in the real build.)
Prints the figures the SRS quotes so the AI-built pipeline can be checked against them."""
import sys, openpyxl, pandas as pd
from collections import Counter
from packed_parser import *

def load_packed(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = list(rows_from_sheet(wb.worksheets[0]))
    assert is_packed(rows), f"{path} is not packed"
    return parse_packed(rows)

prof_p, out_p, cert_p, moo_p = sys.argv[1:5]
res = {}
h, rec, q, st = load_packed(prof_p); res["profile_stats"] = st
P = pd.DataFrame([[i] + r for i, r in rec], columns=["_row"] + h)
h2, rec2, q2, st2 = load_packed(out_p); res["outcomes_stats"] = st2
O = pd.DataFrame([[i] + r for i, r in rec2], columns=["_row"] + h2)
C = pd.read_excel(cert_p, dtype=object)
M = pd.read_excel(moo_p)
res["fingerprints"] = {n: classify_report(d.columns) for n, d in
                       [("profile", P), ("outcomes", O), ("certificate", C), ("moodle", M)]}
for n, d, col in [("profile", P, "Student: Party ID"), ("outcomes", O, "Student: Party ID"), ("certificate", C, "Student: Party ID")]:
    r = d[col].astype(str).map(resolve_id)
    res[f"{n}_id_status"] = dict(Counter(x[0] for x in r))
    res[f"{n}_colleges"] = dict(Counter(x[1] for x in r if x[0] == "OK"))
    d["college"] = [x[1] for x in r]; d["core"] = [x[2] for x in r]; d["idstatus"] = [x[0] for x in r]
Pk = P[P.idstatus == "OK"].copy()
res["profile_students"] = Pk["core"].nunique()
Pk["prog"] = Pk["Program: Code"].str.strip().str.upper()
Pk["sd"] = Pk["Student: Start Date"].str.strip()
key = ["college", "core", "prog", "sd"]
vals = ["Student: Enrolment Status", "Student: Target End Date", "Student: End Date",
        "Student: Total Units Enrolled", "Student: Total Units Completed"]
d = Pk[Pk.duplicated(key, keep=False)]
ex = d.groupby(key).apply(lambda x: x[vals].drop_duplicates().shape[0] == 1)
res["profile_enrolment_dup_groups"] = int(len(ex)); res["profile_exact"] = int(ex.sum()); res["profile_conflicts"] = int((~ex).sum())
Ok = O[O.idstatus == "OK"].copy()
Ok["unit"] = Ok["Student Unit Status: Code"].map(norm_unit)
Ok = Ok[Ok.unit.notna()]
Ok["k"] = (Ok.college + "|" + Ok.core + "|" + Ok["Program: Code"].str.upper().str.strip() + "|" + Ok["Student: Start Date"].str.strip()
           + "|" + Ok.unit + "|" + Ok["Student Unit Status: Start Date"].str.strip())
d2 = Ok[Ok.k.duplicated(keep=False)]
oc = d2.groupby("k")["Student Unit Status: Outcome"].nunique()
res["outcomes_unit_dup_groups"] = int(len(oc)); res["outcomes_exact"] = int((oc == 1).sum()); res["outcomes_conflicts"] = int((oc > 1).sum())
M["linked"] = M.student_rto_id.astype(int) > 0
res["moodle_rows"] = len(M); res["moodle_unlinked_rows"] = int((~M.linked).sum())
mc = {moodle_core(x) for x in M[M.linked].student_rto_id}
res["moodle_real_students"] = len(mc)
res["moodle_not_in_profile"] = len(mc - set(Pk["core"]))
res["moodle_min_total_assessments"] = int(M.count_total_assessments.min())
bad = Pk["Student: Target End Date"].map(lambda v: parse_date(v) is None and str(v).strip() != "")
res["profile_invalid_target_dates"] = int(bad.sum())
for k, v in res.items():
    print(f"{k}: {v}")
