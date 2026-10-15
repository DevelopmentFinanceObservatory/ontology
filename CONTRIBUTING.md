# Contributing

Issues and pull requests are welcome. The ONE Data team maintains this repository. Open an issue to discuss a large change before you write it.

By taking part you agree to the [Code of Conduct](https://github.com/DevelopmentFinanceObservatory/.github/blob/main/CODE_OF_CONDUCT.md). Report security problems through GitHub private vulnerability reporting (the "Report a vulnerability" button under the Security tab), as described in the [security policy](https://github.com/DevelopmentFinanceObservatory/.github/blob/main/SECURITY.md), and not in a public issue. [SUPPORT.md](https://github.com/DevelopmentFinanceObservatory/.github/blob/main/SUPPORT.md) lists where to ask questions.

## Propose a concept or a correction

This repository holds the compiler. The ontology is written and maintained on the [DFO wiki](https://developmentfinance.wikibase.cloud), so a new term, a changed definition or a wrong code in the ontology starts as an issue here. State what you want changed and why, and link the wiki page it concerns. A maintainer makes the edit on the wiki. Pull requests cannot change the concepts.

## Where to raise what

| If you want to…                                                        | Raise it at                                                                                        |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| report a figure that looks wrong, or ask how a source is modelled      | the feedback form on the [DFO website](https://developmentfinance.org)                             |
| request a new source or dataset                                        | "Submit Request" on the [roadmap](https://developmentfinance.org/data/roadmap)                     |
| report a problem with a concept, property or code list in the ontology | an issue in this repository                                                                        |
| report a bug in the compiler or an error in these docs                 | an issue in this repository                                                                        |
| report a bug or failing step in a pipeline                             | an issue in the [pipelines repository](https://github.com/DevelopmentFinanceObservatory/pipelines) |
| improve an agent skill                                                 | an issue in the [skills repository](https://github.com/DevelopmentFinanceObservatory/skills)       |

## Contributing code

Set up with [uv](https://docs.astral.sh/uv/) and Python 3.13 or later. Reading the wiki needs network access but no credentials, so the tests and a compile of `prod` run without access to ONE's cloud project.

```bash
uv sync
uv run pre-commit install
```

Before you open a pull request, run the checks CI runs:

```bash
just check    # ruff lint, ruff format check, ty and pytest
just fmt      # fix lint and formatting
```

Without `just`, run the four commands in the `justfile`.

Branch from `dev` and open the pull request against `dev`. Each pull request addresses a single issue. Commit messages and pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/).

A pull request needs passing CI, tests for changed behaviour, and updated docs. A change to a validation rule updates [docs/validation.md](docs/validation.md). If a change alters compiled output, update the files in `tests/goldens/`.

[docs/development.md](docs/development.md) has the source layout, the dev wiki and the CI setup.
