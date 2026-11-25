"""Build the analysis file from the HSLS:09 student file.

Run from the project root:  uv run python scripts/hsls/02_clean.py

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
1 for an answer, missing for nonresponse. A row with fill = <name>=<value>
takes that value wherever it is still missing and the named variable is
observed. A row with within = <flag> is missing wherever that flag is not 1.

Only the listed codes become missing. Several variables, such as the SES
composite, have real negative values, so "negative means missing" would drop
real data.
"""

import framework as fw
import pandas as pd

fw.scaffold()

crosswalk = fw.data_read("inputs.public.raw.hsls_crosswalk", col_types="c" * 14).fillna("")


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
    # A blank cell is missing too, so a flag never reads it as an answer
    missing = source.isin(codes(row.missing)) | source.isna()
    skipped = source.isin(codes(row.skip))
    if row.derive == "applies":
        column = (~skipped).astype(float).mask(missing)
    else:
        column = source.mask(missing | skipped).replace(pairs(row.recode))
    if row.fill:
        other, value = row.fill.split("=", 1)
        column = column.mask(column.isna() & clean[other].notna(), float(value))
    if row.within:
        column = column.where(clean[row.within] == 1)
    clean[row.name] = column

# Saved to the file its catalog entry names. framework-py 0.1.0.dev26 rewrites an
# existing entry when data_save() is given its name (dropping its description),
# so pass the entry's path until a release with the fix; then this becomes
# fw.data_save(clean, "inputs.private.final.hsls_clean").
fw.data_save(clean, str(fw.data_info("inputs.private.final.hsls_clean").path))
print(f"{len(clean):,} students, {clean.shape[1]} variables")
