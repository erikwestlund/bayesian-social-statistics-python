"""Download the HSLS:09 public-use file from NCES and extract it.

Run from the project root:  uv run python scripts/01_fetch_hsls.py

By downloading, you accept the NCES data usage agreement: use the data for
statistical purposes only, make no attempt to identify anyone, and do not link
it to individually identifiable data.
"""

import hashlib
import urllib.request
import zipfile
from pathlib import Path

import framework as fw

URL = "https://nces.ed.gov/EDAT/Data/Zip/HSLS_2016_v1_0_CSV_Datasets.zip"
SHA256 = "a4de968eefbac25a2b6f7337931f8c8051ddfcd2fd82920041a3c8abbebbd4aa"

fw.scaffold()
folder = Path(fw.project_root()) / "inputs/private/raw/hsls"
archive = folder / "HSLS_2016_v1_0_CSV_Datasets.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


folder.mkdir(parents=True, exist_ok=True)
if not archive.exists():
    print(f"Downloading {URL} (about 270 MB)")
    urllib.request.urlretrieve(URL, archive)

if sha256(archive) != SHA256:
    raise SystemExit(f"{archive} does not match the expected SHA-256. Delete it and run again.")

with zipfile.ZipFile(archive) as zipped:
    for member in zipped.namelist():
        if not (folder / member).exists():
            zipped.extract(member, folder)

print(f"HSLS:09 files are in {folder}")
