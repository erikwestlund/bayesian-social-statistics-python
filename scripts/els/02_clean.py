"""Build the analysis file from the ELS:2002 student file.

Run from the project root:  uv run python scripts/els/02_clean.py

shared/data_spec/els.csv drives every step: which NCES variables
to keep, missing-value codes, recodes, and the new names. The names follow the
HSLS:09 data spec, so code written for one study reads the other. The R,
Python, and Stata projects all read it, so all three build the same file.

A row's missing codes are nonresponse; its skip codes mark a survey component
that did not apply. Both become missing values. A row with fill =
<name>=<value> takes that value wherever it is still missing and the named
variable is observed. Only the listed codes become missing: several
composites, such as SES, have real negative values.
"""

import framework as fw
import numpy as np
import pandas as pd

fw.scaffold()

data_spec = fw.data_read("inputs.public.raw.els_data_spec", dtype=str, keep_default_na=False)


def codes(text: str) -> list[float]:
    """'-9;-8' as [-9, -8]."""
    return [float(code) for code in text.split(";")] if text else []


def pairs(text: str) -> dict[float, float]:
    """'1=0;2=1' as {1: 0, 2: 1}."""
    if not text:
        return {}
    return {float(old): float(new) for old, new in (pair.split("=", 1) for pair in text.split(";"))}


def labelled(text: str) -> set[float]:
    """The values '1=City;2=Suburb' labels: {1, 2}."""
    return {float(pair.split("=", 1)[0]) for pair in text.split(";")} if text else set()


raw = fw.data_read(
    "inputs.private.raw.els_student",
    usecols=list(dict.fromkeys([*data_spec["nces"], "SCH_ID"])),
    dtype={"STU_ID": str},
)

clean = pd.DataFrame(index=raw.index)
for row in data_spec.itertuples():
    source = raw[row.nces]
    # A blank cell is missing too, so a flag never reads it as an answer
    missing = source.isin(codes(row.missing)) | source.isna()
    skipped = source.isin(codes(row.skip))
    column = source.mask(missing | skipped)
    if row.recode:
        column = column.replace(pairs(row.recode))
    if row.fill:
        other, value = row.fill.split("=", 1)
        column = column.mask(column.isna() & clean[other].notna(), float(value))
    allowed = labelled(row.labels)
    if allowed and (column.notna() & ~column.isin(allowed)).any():
        raise SystemExit(f"Unlabelled value in {row.name}")
    clean[row.name] = column

# Every reserve code the data spec does not list would pass through as a value.
# These variables have no real negative values, so any left is a code the
# data spec missed.
real_negatives = {"student_id", "w1_ses", "w1_ses_duncan", "w4_ses"}
nonnegative = [name for name in data_spec["name"] if name not in real_negatives]
leftover = [name for name in nonnegative if (clean[name] < 0).any()]
if leftover:
    raise SystemExit(f"Unlisted negative codes in: {', '.join(leftover)}")

assert (raw["SCH_ID"] == -5).all()
assert clean["student_id"].notna().all() and not clean["student_id"].duplicated().any()
assert not data_spec["name"].duplicated().any()
assert clean["stratum"].notna().all() and clean["stratum"].nunique() == 361
assert clean["psu"].isin([1, 2, 3]).all()
# PSU occupies one digit in the NCES design key (2006-344, appendix G).
clean["school_id"] = 10 * clean["stratum"] + clean["psu"]
sizes = clean["school_id"].value_counts()
print(f"{len(sizes)} base-year school clusters, median size {sizes.median():g}")

components = [
    "w1_income_imputed",
    "w1_mother_edu_imputed",
    "w1_father_edu_imputed",
    "w1_mother_occ_imputed",
    "w1_father_occ_imputed",
]
# Missing when SES is missing or any component flag is missing, as in R
imputed = clean[components].sum(axis=1, skipna=False)
clean["w1_ses_imputed"] = (imputed > 0).astype(float).where(imputed.notna() & clean["w1_ses"].notna())
assert (clean["w2_math"].isna() == clean["w2_test_status"].isin([0, 4])).all()
flagged = clean["w2_math_imputed"].notna()
assert (clean.loc[flagged, "w2_math_imputed"] == clean.loc[flagged, "w2_test_status"].isin([2, 3])).all()
assert (clean["w1_ses_imputed"].isna() == clean["w1_ses"].isna()).all()

# The separate NCES replicate file uses the same student key as the student file.
by_names = [f"BYSTU{i}" for i in range(1, 201)]
f1_names = [f"F1PNL{i}" for i in range(1, 201)]
replicates = fw.data_read(
    "inputs.private.raw.els_brr",
    usecols=["STU_ID", *by_names, *f1_names],
    dtype={"STU_ID": str},
)
key = replicates["STU_ID"]
assert key.notna().all() and not key.duplicated().any()
assert set(key) == set(clean["student_id"])
weights = replicates.set_index("STU_ID").loc[clean["student_id"], [*by_names, *f1_names]]
assert np.isfinite(weights.to_numpy()).all() and (weights.to_numpy() >= 0).all()
weights.columns = [f"w1_weight_rep{i}" for i in range(1, 201)] + [f"w2_weight_panel_rep{i}" for i in range(1, 201)]
clean = pd.concat([clean, weights.reset_index(drop=True).set_axis(clean.index)], axis=1)

fw.data_save(clean, str(fw.data_info("inputs.private.final.els_clean").path))
print(f"{len(clean):,} students, {clean.shape[1]} variables")
