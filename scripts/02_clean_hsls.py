"""Build the analysis file from the HSLS:09 student file.

Run from the project root:  uv run python scripts/02_clean_hsls.py

inputs/public/raw/hsls_crosswalk.csv drives every step: which NCES variables
to keep, missing-value codes, recodes, and the new names. The Stata and R
projects keep the same crosswalk, so all three build the same file.

NCES marks missing values with negative reserve codes, and the crosswalk
splits them in two (see docs/missing-data.md):

- missing: nonresponse (-9, -8, -4, ...). The question applied but went
  unanswered. Analyses impute these or model them.
- skip: logical skips (-7, -6). The question did not apply, such as parent 2
  education in a one-parent family. Analyses usually drop these cases.

Both become missing values, so a flag keeps the difference. A row with
derive = "applies" builds a 0/1 flag from its source: 0 for a logical skip,
1 for an answer, missing for nonresponse. A row with within = <flag> is
missing wherever that flag is not 1.

Only the listed codes become missing. Several variables, such as the SES
composite, have real negative values, so "negative means missing" would drop
real data.
"""

import pandas as pd

import framework as fw

fw.scaffold()

crosswalk = fw.data_read("inputs.public.raw.hsls_crosswalk", col_types="c" * 13).fillna("")


def codes(text: str) -> list[float]:
    """'-9;-8' as [-9, -8]."""
    return [float(code) for code in text.split(";")] if text else []


def pairs(text: str) -> dict[float, float]:
    """'1=0;2=1' as {1: 0, 2: 1}."""
    if not text:
        return {}
    return {float(old): float(new) for old, new in (pair.split("=", 1) for pair in text.split(";"))}


raw = fw.data_read(
    "inputs.private.raw.hsls_student",
    usecols=list(dict.fromkeys(crosswalk["nces"])),
    dtype={"STU_ID": str},
)

clean = pd.DataFrame(index=raw.index)
for row in crosswalk.itertuples():
    source = raw[row.nces]
    missing = source.isin(codes(row.missing))
    skipped = source.isin(codes(row.skip))
    if row.derive == "applies":
        column = (~skipped).astype(float).mask(missing)
    else:
        column = source.mask(missing | skipped).replace(pairs(row.recode))
    if row.within:
        column = column.where(clean[row.within] == 1)
    clean[row.name] = column

fw.data_save(clean, "inputs/private/final/hsls_clean.csv")
print(f"{len(clean):,} students, {clean.shape[1]} variables")
