# DFO ontology

The compiler for the ontology of the
[Development Finance Observatory](https://developmentfinance.org/) (DFO), which turns the
ontology into schema for the DFO's Data Commons.

The DFO ontology is a model of development finance and the semantic layer of the DFO. It
names the concepts in the domain and defines how they relate to each other. The ontology
holds concepts, not figures, and is written and maintained in Wikibase at
**[developmentfinance.wikibase.cloud](https://developmentfinance.wikibase.cloud)**.

This repository holds the compiler that reads the ontology from Wikibase, validates it,
and writes it as [MCF](https://github.com/datacommonsorg/data/blob/master/docs/mcf_format.md),
the format Data Commons uses for schema.

## Browse the ontology

The wiki can be read without an account.

- [Main page](https://developmentfinance.wikibase.cloud/wiki/Main_Page): a starting point
  for exploring the ontology.
- [DFO ontology overview](https://developmentfinance.wikibase.cloud/wiki/Help:DFO_ontology_overview):
  what the ontology holds and how its concepts relate.
- [Editor guide](https://developmentfinance.wikibase.cloud/wiki/Help:Editor_guide): for
  people who add or change concepts.
- [Query service](https://developmentfinance.wikibase.cloud/query/): SPARQL access to the
  whole ontology.

## How the compiler works

Each concept on the wiki becomes one MCF node. Its label, description and aliases become
the node's `name`, `description` and `alternateName`, and its statements become the
node's properties. For example, the
[loan](https://developmentfinance.wikibase.cloud/wiki/Item:Q921) item compiles to:

```text
Node: dcid:Loan
typeOf: dcid:FinancingResourceEnum
name: "loan"
description: "Direct, non-tradable credit repaid over time on agreed terms."
specializationOf: dcid:DebtInstrument
```

Where Data Commons already defines a concept, such as `Country` or `Organization`, the
wiki refers to it by its dcid instead of defining it again, and the compiler emits no
node for it.

The compiler reads the whole wiki and validates the entire graph before writing
anything. If any check fails, it writes no MCF, and the report lists every problem along
with the item it concerns.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 or later.

```bash
uv sync
uv run dfo-ontology compile --bench prod
```

`--bench` selects the wiki to read; `prod` is the published ontology at
developmentfinance.wikibase.cloud. Reading requires network access but no credentials.
The run writes three files to `output/prod/`:

- `dfo.mcf`: the schema, one node per concept, with a header comment naming the wiki it
  was compiled from.
- `codes.csv`: a mapping from publishers' codes, such as CRS purpose codes or ISO
  currency codes, to the dcids they stand for, which pipelines use to translate the
  codes in source data. See [docs/code-mapping.md](docs/code-mapping.md).
- `report.txt`: a summary of the run, covering what was compiled, code coverage,
  provisional nodes and advisories, or every error when the run fails. See
  [docs/validation.md](docs/validation.md) for what each rule checks and how to fix it.

`report.txt` is always written. A failing run writes no MCF or `codes.csv` and deletes
any left by an earlier run, so the output folder never holds files that contradict the
report.

| option                  | effect                                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------------- |
| `--check`               | Validate and write the report, without the MCF or `codes.csv`.                                      |
| `--exclude-provisional` | Leave provisional nodes out of the MCF and `codes.csv`.                                             |
| `-o PATH`               | Write the MCF to `PATH`, with `report.txt` and `codes.csv` beside it, instead of `output/<bench>/`. |

Nodes flagged `isProvisional` on the wiki are not final: their name, description or
place in the model may still change. The report lists them, and they are included in the
output unless `--exclude-provisional` is passed. That run fails (rule E1) if a node that
remains depends on one that was left out.

| exit code | meaning                                                                                  |
| --------- | ---------------------------------------------------------------------------------------- |
| 0         | Validation passed.                                                                       |
| 1         | Validation failed. The report is also written to stderr.                                 |
| 2         | The wiki could not be read, the output could not be written, or the command was invalid. |

## Development

The dev wiki, [dfo-dev.wikibase.cloud](https://dfo-dev.wikibase.cloud), is a working
copy of the ontology where changes are tested before they are made on prod. Compile it
with `--bench dev`; its output goes to `output/dev/`.

The compiler lives in `src/dfo_ontology/`: `reader.py` reads the wiki, `validate.py`
runs the checks in `rules/`, and `emit.py`, `codes.py` and `report.py` write the three
output files.

With [just](https://github.com/casey/just) installed:

```bash
just check            # ruff lint, ruff format check, ty and pytest, as in CI
just fmt              # fix lint and formatting
just compile prod     # compile a wiki; options go after the name
```

Run `uv run pre-commit install` once to install the commit hooks. They run ruff, ty,
codespell and a Markdown formatter, but not the tests. Some hooks rewrite files, so
re-run the tests after a hook changes anything.
