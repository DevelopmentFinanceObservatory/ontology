# Code mapping

`codes.csv` maps the codes publishers use to the DFO nodes they stand for. A data
pipeline reads it to turn a code in raw data, such as a DAC provider code, into the dcid
of the node it means, without parsing the MCF.

The compiler writes it next to `dfo.mcf` on every passing run that is not `--check`. It
has no comment line, so it loads as a plain CSV.

## Columns

| column     | holds                                                                      |
| ---------- | -------------------------------------------------------------------------- |
| `list`     | The value list or class the entity belongs to.                             |
| `code`     | The code, verbatim.                                                        |
| `dcid`     | The dcid of the node the code stands for, in the same form as the MCF.     |
| `label`    | The entity's label, for a person reading the file.                         |
| `property` | The property that states the code, which names the codelist it comes from. |

There is one row per code. An entity with codes in several codelists gets a row for each,
all naming the same dcid. Items that refer to a Data Commons node, such as countries,
get rows too, even though they emit nothing into the MCF.

## Joining

Join on `list`, `code` and `property` together. A code means something only within its
codelist and list: the same code can stand for different things in different codelists,
or for a currency and an organisation within one codelist.

The `Codes` section of `report.txt` shows, for each list, how many of its members carry
a code and names the ones that do not.
