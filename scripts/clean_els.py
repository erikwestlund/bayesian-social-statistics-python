"""Build the ELS:2002 analysis file: run every step in scripts/els/ in order.

Run from the project root:  uv run python scripts/clean_els.py

Each step is a script that also runs on its own. A step that fails stops the
run, so later steps never read a half-built file.
"""

import runpy
from pathlib import Path

for step in sorted(Path("scripts/els").glob("[0-9]*_*.py")):
    print(f"Running {step}", flush=True)
    runpy.run_path(str(step), run_name="__main__")
