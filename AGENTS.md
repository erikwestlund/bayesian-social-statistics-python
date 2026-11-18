# bayesian-social-statistics-python

This file provides guidance to AI assistants working with this Framework project.
It is the canonical context file; detailed workflow instructions live in the
skills listed below. Edit the sections without regeneration markers freely -
they won't be overwritten.

This project holds restricted data. Do not read or print files in `inputs/private/`, `outputs/private/`. Work from the data dictionary and simulated data instead.

## Skills

Detailed instructions live in skill files, loaded on demand. Claude Code discovers
them automatically; other agents should read the relevant SKILL.md before working
on a matching task.

| Skill | Covers | Path |
|-------|--------|------|
| `framework-workflow` | Framework package initialization and notebook or script creation | `.agents/skills/framework-workflow/SKILL.md` |
| `framework-data` | reading and saving data with data_read() and data_save() | `.agents/skills/framework-data/SKILL.md` |
| `framework-packages` | adding and managing Python packages with package_add() | `.agents/skills/framework-packages/SKILL.md` |
| `framework-outputs` | saving results with the Framework package | `.agents/skills/framework-outputs/SKILL.md` |
| `framework-sensitive-data` | private and public folders in a privacy-sensitive project | `.agents/skills/framework-sensitive-data/SKILL.md` |
| `matplotlib-figures` |  | `.agents/skills/matplotlib-figures/SKILL.md` |
| `writing` |  | `.agents/skills/writing/SKILL.md` |
| `git-workflow` |  | `.agents/skills/git-workflow/SKILL.md` |
| `jupyter-notebooks` |  | `.agents/skills/jupyter-notebooks/SKILL.md` |

## Framework Environment <!-- @framework:regenerate -->

This project uses the Framework Python package. Follow its conventions in code that
calls `fw.scaffold()`. Leave existing code as it is unless the user asks you to
change it.

### scaffold()

Start each notebook and script with `import framework as fw` and `fw.scaffold()`. It:

1. Finds the project root and loads `.env` and the settings. The working directory stays as it is.
2. Creates framework.db if needed and records the scaffold time
3. Puts `functions/` on the import path, so its modules import directly
4. Runs `scaffold.py` from the project root, if there is one
5. Sets the random seed to 123

### Conventions

- Prefer `fw.package_add("name")` to `pip install`. It records the package in pyproject.toml.
- Put helpers shared between notebooks in `functions/` and import them.
- Prefer the project's seed. When an operation needs its own seed, say why in a comment.
- Ask before running a database statement that changes data.
- Ask before publishing anything public. GitHub Pages is public even from a private repository.

## Installed Packages <!-- @framework:regenerate -->

**Dependencies** (in pyproject.toml): framework-py, seaborn, matplotlib, ipykernel, nbformat, nbclient, jupyterlab

Add packages with `fw.package_add("name")`.

## Data Management <!-- @framework:regenerate -->

Prefer `fw.data_read()` and `fw.data_save()` for project data. They record a hash
of each file. This project's data directories:

| Purpose | Directory |
|---------|-----------|
| Private raw data | `inputs/private/raw/` |
| Public raw data | `inputs/public/raw/` |
| Private intermediate | `inputs/private/intermediate/` |
| Public intermediate | `inputs/public/intermediate/` |
| Private analysis-ready | `inputs/private/final/` |
| Public analysis-ready | `inputs/public/final/` |
| Private tables | `outputs/private/tables/` |
| Public tables | `outputs/public/tables/` |
| Private figures | `outputs/private/figures/` |
| Public figures | `outputs/public/figures/` |

## Private Folders

This project was created as privacy sensitive. Private files go in the
`private/` folders, which Git ignores. The `framework-sensitive-data` skill
describes the folders and the checks Framework runs.

## Project Notes

*Add your project-specific notes, conventions, and documentation here.*
