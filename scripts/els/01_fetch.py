"""Download the ELS:2002 public-use file and its documentation from NCES.

Run from the project root:  uv run python scripts/els/01_fetch.py

By downloading, you accept the NCES data usage agreement: use the data for
statistical purposes only, make no attempt to identify anyone, and do not link
it to individually identifiable data.

Each file goes where its entry in settings/data.yml says, so a file is renamed
or moved there, not here. The data go under inputs/private/raw and stay out of
git. The NCES documentation goes under inputs/public/raw/els_docs, which git
also ignores because the PDFs are large. Every download is checked against its
SHA-256 before it takes its final name, and every file extracted from a zip is
checked against the zip's own length and CRC, so an interrupted run leaves
nothing behind that a later run would trust.

The replicate weights come as CSV. The R project reads the SPSS copy of the
same file; NCES publishes both, with the same values.
"""

import hashlib
import shutil
import urllib.request
import zipfile
import zlib
from pathlib import Path

import framework as fw

# (catalog name, URL, SHA-256)
DOWNLOADS = [
    (
        "inputs.private.raw.els_zip",
        "https://nces.ed.gov/EDAT/Data/Zip/ELS_2002-12_v1_0_CSV_Datasets.zip",
        "b255f2c1821618cd7039f5ab7c4e6ed92caa536598cffc383b4f012deba411fb",
    ),
    (
        "inputs.private.raw.els_brr_zip",
        "https://nces.ed.gov/EDAT/Data/Zip/ELS_2002-12_PETS_v1_0_Student_BRR_CSV_Datasets.zip",
        "019002a44f547dc44f03df024939b27c001219f3af401c8a59fa21863f67ecc0",
    ),
    (
        "inputs.public.raw.els_doc_base_year",
        "https://nces.ed.gov/pubs2004/2004405.pdf",
        "af28f1cc9d91b9f67269fb3009ab269bc746de3572e782b1759f3cb59771e161",
    ),
    (
        "inputs.public.raw.els_doc_first_follow_up",
        "https://nces.ed.gov/pubs2006/2006344.pdf",
        "0e2dea9236a2a766635e6d20d5d5d30df2d1bddedc123c71c29163435f036aa1",
    ),
    (
        "inputs.public.raw.els_codebook_first_follow_up",
        "https://nces.ed.gov/pubs2006/2006344_4.pdf",
        "d97d18706978a81765ec0deb9cc0b706b7e4bfa1c19622846a3f4f77b8217be2",
    ),
    (
        "inputs.public.raw.els_doc_third_follow_up",
        "https://nces.ed.gov/pubs2014/2014364.pdf",
        "5b897f7d252eb8529ac492350d93b7c675576af66e6dbcafea1a15d63e8deeed",
    ),
]

# The files each zip holds that the series uses, by the catalog name each is
# extracted to
MEMBERS = {
    "inputs.private.raw.els_zip": {
        "els_02_12_byf3stu_v1_0.csv": "inputs.private.raw.els_student",
        "els_02_12_byf1sch_v1_0.csv": "inputs.private.raw.els_school",
    },
    "inputs.private.raw.els_brr_zip": {
        "els_02_12_byf3stubrr_v1_0.csv": "inputs.private.raw.els_brr",
    },
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


def extract(archive: Path, members: dict[str, str]) -> None:
    """Extract the listed members to their catalog entries' files unless complete copies are there."""
    with zipfile.ZipFile(archive) as zipped:
        listed = {member.filename: member for member in zipped.infolist()}
        missing = set(members) - set(listed)
        if missing:
            raise SystemExit(f"{archive} lacks {sorted(missing)}.")
        for filename, name in members.items():
            member = listed[filename]
            target = located(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size == member.file_size and crc32(target) == member.CRC:
                continue
            print(f"Extracting {filename} to {target}")
            partial = target.with_name(target.name + ".part")
            with zipped.open(member) as source, partial.open("wb") as copy:
                shutil.copyfileobj(source, copy, 1 << 20)
            partial.replace(target)


for name, url, expected in DOWNLOADS:
    fetch(located(name), url, expected)

for archive, members in MEMBERS.items():
    extract(located(archive), members)

root = fw.project_root().resolve()
names = [name for name, _, _ in DOWNLOADS] + [n for members in MEMBERS.values() for n in members.values()]
for name in names:
    print(f"{name}: {located(name).relative_to(root)}")
