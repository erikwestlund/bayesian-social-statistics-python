"""Download and extract the NCES files that shared/data_locations.csv lists,
for one data set, such as fetch_data("els"), or for all of them.

The file has one row per file: dataset, path (where it goes, relative to the
project root), url (where to download it) or from (the zip, another row's
path, to extract it from), and its sha256. The crc and bytes columns are for
Stata, which has no SHA-256.

A file already in place is checked, not fetched again. A download or an
extracted file takes its final name only after its SHA-256 matches, so an
interrupted run leaves nothing behind that a later run would trust.
"""

import csv
import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

import framework as fw


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_data(dataset: str | None = None, locations: str = "shared/data_locations.csv") -> list[str]:
    """Download or extract every listed file for ``dataset`` (all data sets when None) not already in place."""
    root = Path(fw.project_root())
    with (root / locations).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if dataset is not None:
        if dataset not in {row["dataset"] for row in rows}:
            raise SystemExit(f"{locations} lists no data set {dataset}.")
        rows = [row for row in rows if row["dataset"] == dataset]

    for row in rows:
        target = root / row["path"]
        if target.exists():
            if sha256(target) == row["sha256"]:
                continue
            if row["url"]:
                raise SystemExit(f"{row['path']} does not match the expected SHA-256. Delete it and run again.")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        if row["url"]:
            print(f"Downloading {row['url']}", flush=True)
            urllib.request.urlretrieve(row["url"], partial)
        else:
            print(f"Extracting {target.name} from {Path(row['from']).name}", flush=True)
            with zipfile.ZipFile(root / row["from"]) as zipped, zipped.open(target.name) as source:
                with partial.open("wb") as copy:
                    shutil.copyfileobj(source, copy, 1 << 20)
        if sha256(partial) != row["sha256"]:
            partial.unlink()
            raise SystemExit(f"{row['path']} does not match the expected SHA-256. Run again.")
        partial.replace(target)
    return [row["path"] for row in rows]
