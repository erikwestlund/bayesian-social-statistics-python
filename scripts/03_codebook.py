"""Write docs/codebook.md, the codebook for the cleaned HSLS:09 file.

Run from the project root after 02_clean_hsls.py:
    uv run python scripts/03_codebook.py

The codebook lists each variable in the crosswalk with its NCES source, its
values and their counts, and how often each reserve code occurs, split into
nonresponse and logical skips (see docs/missing-data.md). Counts are
unweighted, over all 23,503 students in the file.

The R and Stata projects keep identical copies of docs/codebook.md. Run this
script again whenever the crosswalk changes, and copy the result to them.
"""

from pathlib import Path

import framework as fw
import pandas as pd

fw.scaffold()

# Reserve codes, from table 38 of NCES 2018-140 (see docs/missing-data.md)
RESERVE = {
    -1: "Don't know",
    -3: "Carry-through missing",
    -4: "Not administered in the abbreviated interview",
    -5: "Suppressed on the public-use file",
    -6: "Survey component not applicable",
    -7: "Item not applicable (logical skip)",
    -8: "Unit nonresponse",
    -9: "Item nonresponse",
}

crosswalk = fw.data_read("inputs.public.raw.hsls_crosswalk", col_types="c" * 14).fillna("")
raw = fw.data_read(
    "inputs.private.raw.hsls_student",
    usecols=list(dict.fromkeys(crosswalk["nces"])),
    dtype={"STU_ID": str},
)
clean = fw.data_read("inputs.private.final.hsls_clean", dtype={"student_id": str})

# The code tables compare raw and clean values row by row, so the two files
# must hold the same students in the same order
if not (raw["STU_ID"].is_unique and raw["STU_ID"].tolist() == clean["student_id"].tolist()):
    raise SystemExit("The raw and clean files do not list the same students in the same order.")


def codes(text: str) -> list[float]:
    return [float(code) for code in text.split(";")] if text else []


def labels(text: str) -> dict[float, str]:
    """'1=City;2=Suburb' as {1: 'City', 2: 'Suburb'}."""
    if not text:
        return {}
    return {float(value): label for value, label in (pair.split("=", 1) for pair in text.split(";"))}


def number(value: float) -> str:
    """A code or value as written: 2, not 2.0. A minus sign for negatives."""
    text = f"{value:g}"
    return text.replace("-", "−")


def count(n: int) -> str:
    return f"{n:,}"


def anchor(name: str) -> str:
    """The fragment GitHub gives the heading '## name'. It keeps underscores."""
    return name.lower()


def values_section(row, column: pd.Series) -> list[str]:
    observed = column.dropna()
    lines = []
    if row.type == "id":
        lines.append(f"{count(observed.nunique())} distinct values, one per student.")
    elif row.type == "weight":
        positive = observed[observed > 0]
        lines.append(
            f"{count(len(positive))} students have a weight above 0, "
            f"from {positive.min():,.2f} to {positive.max():,.2f}. "
            f"{count(int((observed == 0).sum()))} have a weight of 0 and add nothing "
            "to an estimate that uses this weight."
        )
    elif row.type == "continuous":
        lines.append(
            f"{count(len(observed))} observed. Mean {observed.mean():.2f}, "
            f"SD {observed.std():.2f}, range {number(round(observed.min(), 2))} "
            f"to {number(round(observed.max(), 2))}."
        )
    else:
        value_labels = labels(row.labels)
        if row.derive == "applies":
            value_labels = {0: "Logical skip in the source variable", 1: "Answered"}
        elif row.type == "binary" and not value_labels:
            value_labels = {0: "No", 1: "Yes"}
        frequencies = observed.value_counts()
        values = sorted(set(frequencies.index) | {v for v in value_labels if v not in codes(row.missing)})
        lines += ["| Value | Label | Count |", "|---:|---|---:|"]
        for value in values:
            lines.append(f"| {number(value)} | {value_labels.get(value, '')} | {count(int(frequencies.get(value, 0)))} |")
    return lines


def source_labels(nces: str) -> dict[float, str]:
    """Value labels for an NCES variable, from any crosswalk row that reads it."""
    merged = {}
    for text in crosswalk.loc[crosswalk["nces"] == nces, "labels"]:
        merged.update(labels(text))
    return merged


def outcome(values: pd.Series) -> str:
    """What a reserve code became in the clean file, such as 'Missing' or '0: 419; missing: 3,619'."""
    counts = values.value_counts(dropna=False)
    names = ["missing" if pd.isna(value) else number(value) for value in counts.index]
    if len(counts) == 1:
        return names[0].capitalize()
    return "; ".join(f"{name}: {count(int(n))}" for name, n in zip(names, counts))


def missing_section(row, source: pd.Series, column: pd.Series) -> list[str]:
    """Count each listed reserve code in the raw file."""
    meanings = source_labels(row.nces)
    rows = []
    for kind, listed in (("Nonresponse", codes(row.missing)), ("Logical skip", codes(row.skip))):
        for code in listed:
            n = int((source == code).sum())
            if n:
                meaning = RESERVE.get(int(code), meanings.get(code, ""))
                becomes = outcome(column[source == code])
                rows.append(f"| {number(code)} | {meaning} | {kind} | {becomes} | {count(n)} |")
    lines = []
    if rows:
        lines += ["| NCES code | Meaning | Kind | Becomes | Count |", "|---:|---|---|---|---:|", *rows]
    if row.within:
        # Students the code table above does not already count
        listed = codes(row.missing) + codes(row.skip)
        extra = int((column.isna() & ~source.isin(listed)).sum())
        if lines:
            lines.append("")
        lines += [f"Also missing wherever `{row.within}` is not 1: {count(extra)} more students."]
    if not lines:
        lines.append("No missing values.")
    return lines


out = [
    "# HSLS:09 codebook",
    "",
    "The variables in `inputs/private/final/hsls_clean.csv`, one row per student",
    f"({count(len(clean))} students). Counts are unweighted. The cleaning scripts build",
    "the file from `inputs/public/raw/hsls_crosswalk.csv`, and `docs/missing-data.md`",
    "explains the reserve codes.",
    "",
    "The NCES code tables count each reserve code in the raw file, so they show",
    "why a value is missing. A reserve code becomes a missing value, except in a",
    "flag built from a logical skip, where the skip becomes 0.",
    "",
    "This file is generated by `scripts/03_codebook.py` in the Python project.",
    "The R and Stata projects keep identical copies.",
    "",
    "| Variable | Label | NCES | Type | Observed |",
    "|---|---|---|---|---:|",
]
for row in crosswalk.itertuples():
    out.append(
        f"| [`{row.name}`](#{anchor(row.name)}) | {row.label} | `{row.nces}` | {row.type} "
        f"| {count(int(clean[row.name].notna().sum()))} |"
    )

for row in crosswalk.itertuples():
    source = raw[row.nces]
    column = clean[row.name]
    details = [f"NCES `{row.nces}`", f"{row.level} level"]
    if row.wave:
        details.append(f"wave {row.wave}")
    if row.source:
        details.append(f"source: {row.source}")
    details.append(row.type)
    out += ["", f"## {row.name}", "", row.label + ".", "", " · ".join(details) + "."]
    if row.derive == "applies":
        out += ["", f"A flag built from `{row.nces}`: 0 where it has a logical-skip code, 1 where it has an answer."]
    if row.recode:
        pairs = ", ".join(
            f"{number(float(old))} → {number(float(new))}"
            for old, new in (pair.split("=", 1) for pair in row.recode.split(";"))
        )
        out += ["", f"Recoded from the NCES values: {pairs}."]
    if row.fill:
        other, value = row.fill.split("=", 1)
        filled = int((source.isin(codes(row.missing) + codes(row.skip)) & (column == float(value))).sum())
        out += ["", f"Set to {value} where still missing and `{other}` is observed ({count(filled)} students)."]
    out += ["", *values_section(row, column), "", *missing_section(row, source, column)]

path = Path(fw.project_root()) / "docs/codebook.md"
path.write_text("\n".join(out) + "\n")
print(f"Wrote {path}")
