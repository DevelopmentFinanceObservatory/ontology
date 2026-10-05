# DFO Ontology

The concept store for the **Development Finance Observatory (DFO)**: a shared, explicit model
of development-finance concepts and how they relate, authored in a Wikibase instance and
compiled to [MCF](https://github.com/datacommonsorg/data/blob/master/docs/mcf_format.md) for
the DFO's custom Data Commons.

This repo produces **schema MCF only** — the concept layer. Observations, source data, and the
statistical pipeline live in separate repos. The compiler reads the whole Wikibase graph,
validates it against the full rulebook, and emits one deterministic MCF file, a
code mapping, and a report.
Nothing is emitted unless every check passes.

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

## Project structure

- `src/dfo_ontology/` — the compiler (reader → validator → emitter → report) and bench tooling
- `tests/` — unit, emitter, and golden-file tests
- `output/<bench>/` — compiled MCF, codes.csv, and run reports (gitignored; regenerated on every run)

## Benches

There are three Wikibase instances, and `compile` reads whichever one you name:

| `--bench` | instance                        | browse                                    |
| --------- | ------------------------------- | ----------------------------------------- |
| `prod`    | Development Finance Observatory | https://developmentfinance.wikibase.cloud |
| `testing` | DFO testing 2                   | https://dfo-testing-2.wikibase.cloud      |
| `dev`     | DFO Dev                         | https://dfo-dev.wikibase.cloud            |

There is no default: a `compile` that names no bench is a usage error, so no run
reads an instance you didn't choose. The report and the MCF record which one they
came from — `report.txt` on its first line, `dfo.mcf` in a comment atop the file;
`codes.csv` stays comment-free so `pandas.read_csv` loads it bare, and the report
beside it names the bench. Each bench writes to its own directory, so compiling
one never overwrites another's output.

## Running the compiler

```bash
# write output/testing/dfo.mcf, codes.csv, and report.txt
uv run dfo-ontology compile --bench testing

# validate and write the report, skip the MCF
uv run dfo-ontology compile --bench prod --check

# leave nodes flagged isProvisional out of the MCF and codes.csv
uv run dfo-ontology compile --bench prod --exclude-provisional
```

Reading a bench is unauthenticated — `compile` and `compile --check` both need
network access but no credentials. `-o/--output` moves all three artifacts and drops
the per-bench directory: `uv run dfo-ontology compile --bench prod -o build/dfo.mcf`
writes `build/dfo.mcf`, `build/codes.csv`, and `build/report.txt`.

A node flagged `isProvisional` → True is not final yet, and a passing report
lists every one under `Provisional`. They are written to the MCF and codes.csv
like any other node unless `--exclude-provisional` is given. Leaving them out
fails the run (E1) if a node that stays in would point at one.

`report.txt` is always written, whether the run passes or fails. `dfo.mcf` and
`codes.csv` are written only when validation passes and `--check` wasn't given —
the compiler never emits for a graph that failed a check, and a failing run
deletes anything an earlier run left behind rather than leaving artifacts that
read as current. Exit codes:

| code | meaning                                                                                                                                                 |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | success — validation passed (and the MCF and codes.csv were written, unless `--check`)                                                                  |
| 1    | validation failed — no MCF, the report went to stderr too                                                                                               |
| 2    | the bench couldn't be read, the output path couldn't be written, or the command-line usage was wrong (no subcommand, no `--bench`, or an unknown bench) |

See [`docs/validation.md`](docs/validation.md) for what every rule id in a
report checks and how to fix it.

## The code mapping

`codes.csv` maps source codes to the DFO dcids they stand for, so a data
pipeline can translate the codes in raw data (a CRS purpose column holding
"120", a DAC provider column holding "913") into references to our schema
nodes without parsing MCF:

```csv
list,code,dcid,label,property
dcid:CRSPurposeEnum,120,dcid:CRSPurposeHealth,health (CRS purpose),classificationCode
dcid:CurrencyUnit,918,dcid:CurrencyEUR,Euro,dacCode
dcid:Organization,918,dcid:EuropeanUnionInstitutions,European Union institutions,dacCode
```

Dcids carry the same namespace prefix the MCF uses — whichever one the compiler
is set to mint under.

One row per code stated on the bench, sorted by (list, code, dcid). Entities
without a code produce no row — most lists we mint mirror no external scheme,
so none of their values carry one.

- **list** — the value list or class the code was assigned within, named by its
  dcid. A code means something only inside its own set, so a consumer filters by
  this before joining. A class counts as much as a value list, and a class that
  is a reference to a base graph node is named by the dcid it carries. The
  column is empty only when the entity's `typeOf` does not resolve.
- **code** — the code literal, verbatim.
- **dcid** — the entity's own dcid.
- **label** — the entity's label, for a human reading the file.
- **property** — which property stated the code: `classificationCode` for a
  value in a coded scheme, `dacCode` for a thing in the DAC register,
  `iso4217AlphaCode` for a currency's ISO code. This is what tells the kinds of
  row apart, and one entity can carry rows of more than one kind: a currency
  renders a row per DAC code it answers to and another for its ISO code, all
  naming the same dcid.

How far uniqueness goes. `(list, code, property)` is the key. A classification
code is unique within its list (G9), and an external register's code is unique
within the class it was assigned to, so the three columns together identify one
dcid. Neither the code alone nor the code with the property is enough: a
register can number two kinds of thing from one sequence, and then only the
class tells the rows apart. That is why the column is filled for every coded
entity rather than for minted value lists alone.

The success report counts coverage for every type that holds a coded entity
("4 of 4 coded") and names any uncoded ones, so a forgotten code statement
shows up at compile time rather than as an unmatched code in the pipeline.

## Code quality

```bash
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run ty check src/dfo_ontology    # type check
uv run pytest                       # tests
```

Pre-commit hooks run these automatically. To run them by hand:

```bash
uv run pre-commit run --all-files
```

## License

MIT — see [LICENSE](LICENSE).
