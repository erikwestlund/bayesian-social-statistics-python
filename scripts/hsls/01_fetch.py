"""Download the HSLS:09 public-use file and its documentation from NCES.

Run from the project root:  uv run python scripts/hsls/01_fetch.py

By downloading, you accept the NCES data usage agreement: use the data for
statistical purposes only, make no attempt to identify anyone, and do not link
it to individually identifiable data.

Each file goes where its entry in settings/data.yml says, so a file is renamed
or moved there, not here. The data go under inputs/private/raw and stay out of
git. The NCES documentation goes under inputs/public/raw/hsls_docs, which git
also ignores because the PDFs are large. Every download is checked against its SHA-256
before it takes its final name, and every file extracted from the zip is
checked against the zip's own length and CRC, so an interrupted run leaves
nothing behind that a later run would trust.
"""

import hashlib
import shutil
import urllib.request
import zipfile
import zlib
from pathlib import Path

import framework as fw

ARCHIVE = "inputs.private.raw.hsls_zip"

# (catalog name, URL, SHA-256)
DOWNLOADS = [
    (
        ARCHIVE,
        "https://nces.ed.gov/EDAT/Data/Zip/HSLS_2016_v1_0_CSV_Datasets.zip",
        "a4de968eefbac25a2b6f7337931f8c8051ddfcd2fd82920041a3c8abbebbd4aa",
    ),
    (
        "inputs.public.raw.hsls_doc_base_year",
        "https://nces.ed.gov/surveys/hsls09/pdf/2011328_1.pdf",
        "888a17c972d8d38350f6084be06fce251666cca9ecba22f2af1359400e8faca9",
    ),
    (
        "inputs.public.raw.hsls_codebook_base_year",
        "https://nces.ed.gov/surveys/hsls09/pdf/2011328_2.pdf",
        "9ad7520cca392a38d392ec29c486c4f1e16f30e8e122bbe02b8c64bf9775cf22",
    ),
    (
        "inputs.public.raw.hsls_codebook_first_follow_up",
        "https://nces.ed.gov/pubs2014/2014361_AppendixI.pdf",
        "7d5588edb241faa3dc3b15d83bee9de3196bb6b5fc7f4ef6e686560f5702c286",
    ),
    (
        "inputs.public.raw.hsls_doc_second_follow_up",
        "https://nces.ed.gov/pubs2018/2018140.pdf",
        "d5a9bef3822b76a964bf5b1ddd095bfbbbea4eb87330a88eb1b050951f6e837b",
    ),
]

# The files in the NCES zip, by the catalog name each is extracted to
MEMBERS = {
    "hsls_16_student_v1_0.csv": "inputs.private.raw.hsls_student",
    "hsls_09_school_v1_0.csv": "inputs.private.raw.hsls_school",
}

fw.scaffold()


def located(name: str) -> Path:
    """Where the catalog entry ``name`` keeps its file."""
    return fw.data_info(name).path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def crc32(path: Path) -> int:
    crc = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            crc = zlib.crc32(block, crc)
    return crc


def fetch(target: Path, url: str, expected: str) -> None:
    """Download url to target unless a checked copy is there."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256(target) != expected:
            raise SystemExit(f"{target} does not match the expected SHA-256. Delete it and run again.")
        return
    partial = target.with_name(target.name + ".part")
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, partial)
    if sha256(partial) != expected:
        partial.unlink()
        raise SystemExit(f"The download of {url} does not match the expected SHA-256. Run again.")
    partial.replace(target)


def extract(archive: Path) -> None:
    """Extract each zip member to its catalog entry's file unless a complete copy is there."""
    with zipfile.ZipFile(archive) as zipped:
        listed = {member.filename for member in zipped.infolist()}
        if listed != set(MEMBERS):
            raise SystemExit(f"{archive} holds {sorted(listed)}, not the files MEMBERS names.")
        for member in zipped.infolist():
            target = located(MEMBERS[member.filename])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == member.file_size and crc32(target) == member.CRC:
                continue
            print(f"Extracting {member.filename} to {target}")
            partial = target.with_name(target.name + ".part")
            with zipped.open(member) as source, partial.open("wb") as copy:
                shutil.copyfileobj(source, copy, 1 << 20)
            partial.replace(target)


for name, url, expected in DOWNLOADS:
    fetch(located(name), url, expected)

extract(located(ARCHIVE))

root = fw.project_root().resolve()
for name in [*MEMBERS.values(), *(name for name, _, _ in DOWNLOADS)]:
    print(f"{name}: {located(name).relative_to(root)}")
