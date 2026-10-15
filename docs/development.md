# Development

Notes for maintainers of the compiler. Contributors can start with [CONTRIBUTING.md](../CONTRIBUTING.md).

## Source layout

The compiler lives in `src/dfo_ontology/`. `reader.py` reads the wiki, `validate.py` runs the checks in `rules/`, and `emit.py`, `codes.py` and `report.py` write the three output files. `config.py` holds the bench URLs and the ids of the bookkeeping properties. Tests are in `tests/`, with fixtures in `tests/fixtures/` and expected output in `tests/goldens/`.

## Benches

A bench is a Wikibase instance the compiler reads, chosen with `--bench`.

| bench  | wiki                                                                           | use                                                                                                     |
| ------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `prod` | [developmentfinance.wikibase.cloud](https://developmentfinance.wikibase.cloud) | The published ontology.                                                                                 |
| `dev`  | [dfo-dev.wikibase.cloud](https://dfo-dev.wikibase.cloud)                       | A working copy where changes are tested before they are made on prod. Its output goes to `output/dev/`. |

## Commands

With [just](https://github.com/casey/just) installed:

```bash
just check            # ruff lint, ruff format check, ty and pytest, as in CI
just fmt              # fix lint and formatting
just compile prod     # compile a wiki; options go after the name
```

## Commit hooks

Run `uv run pre-commit install` once. The hooks run ruff, ty, codespell and a Markdown formatter, but not the tests. Some hooks rewrite files, so re-run the tests after a hook changes anything.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `dev` and `main` and on pull requests against them. A draft pull request runs no jobs, and marking it ready starts the run. The lint job runs `ruff check`, `ruff format --check` and `ty`. The test job runs pytest with coverage on Python 3.13 and 3.14.

## Project template

The repository was generated from a Copier template, and `.copier-answers.yml` records its source and version. Do not edit that file by hand.
