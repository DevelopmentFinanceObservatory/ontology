# DFO ontology

The ontology of development finance for the [Development Finance Observatory](https://github.com/DevelopmentFinanceObservatory) (DFO), and the compiler that turns it into schema for Data Commons.

The ontology names the concepts of the domain, such as loans, debt instruments, currencies and the code lists publishers use, and defines how they relate. It holds concepts, not figures. It is written and maintained in Wikibase at [developmentfinance.wikibase.cloud](https://developmentfinance.wikibase.cloud). This repository holds the compiler that reads it from Wikibase, validates it, and writes it as [MCF](https://github.com/datacommonsorg/data/blob/master/docs/mcf_format.md), the format [Google Data Commons](https://datacommons.org) uses for schema.

The DFO is an initiative of [ONE Data](https://data.one.org), and its public site is [developmentfinance.org](https://developmentfinance.org/). This repository is one part of it, and the [organisation profile](https://github.com/DevelopmentFinanceObservatory) maps the others.

This repository is under active development. Interfaces, schemas, and data may change without notice.

## Browse the ontology

The wiki can be read without an account.

- [Main page](https://developmentfinance.wikibase.cloud/wiki/Main_Page): a starting point for exploring the ontology.
- [DFO ontology overview](https://developmentfinance.wikibase.cloud/wiki/Help:DFO_ontology_overview): what the ontology holds and how its concepts relate.
- [Editor guide](https://developmentfinance.wikibase.cloud/wiki/Help:Editor_guide): for people who add or change concepts.
- [Query service](https://developmentfinance.wikibase.cloud/query/): SPARQL access to the whole ontology.

To propose a new concept or a correction, open an issue and link the wiki page it concerns. See [CONTRIBUTING.md](CONTRIBUTING.md).

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
node for it. The MCF therefore extends the Data Commons schema. It adds the
development-finance concepts and reuses the Data Commons ones.

The compiler reads the whole wiki and validates the entire graph before writing
anything. If any check fails, it writes no MCF, and the report lists every problem along
with the item it concerns.

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13 or later. Nothing here needs ONE's Google Cloud project.

```bash
uv sync
uv run dfo-ontology compile --bench prod
```

`--bench` selects the wiki to read, and `prod` is the published ontology at
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

Nodes flagged `isProvisional` on the wiki are not final. Their name, description or
place in the model may change. The report lists them, and they are included in the
output unless `--exclude-provisional` is passed. That run fails (rule E1) if a node that
remains depends on one that was left out.

| exit code | meaning                                                                                  |
| --------- | ---------------------------------------------------------------------------------------- |
| 0         | Validation passed.                                                                       |
| 1         | Validation failed. The report is also written to stderr.                                 |
| 2         | The wiki could not be read, the output could not be written, or the command was invalid. |

## Documentation

- [docs/validation.md](docs/validation.md): every validation rule, what it checks and how to fix it.
- [docs/code-mapping.md](docs/code-mapping.md): the layout and use of `codes.csv`.
- [docs/development.md](docs/development.md): the source layout, the dev wiki and the maintainer workflow.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT. See [LICENSE](LICENSE).
