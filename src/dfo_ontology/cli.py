"""`dfo-ontology compile`: read the named bench, validate it, write MCF and a report."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from dfo_ontology import codes, emit, provisional, reader, report, validate
from dfo_ontology.config import BENCHES, Config
from dfo_ontology.model import Graph
from dfo_ontology.reader import BenchError

OUTPUT_ROOT = Path("output")


def default_output(bench: str) -> Path:
    """The bench's own output directory, so one bench never overwrites another's MCF.

    Args:
        bench: the bench name.
    """
    return OUTPUT_ROOT / bench / "dfo.mcf"


def main(argv: Sequence[str] | None = None) -> int:
    """dfo-ontology entry point.

    Args:
        argv: command-line arguments; defaults to sys.argv.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "compile":
        parser.print_usage(sys.stderr)
        return 2

    config = Config(bench=args.bench)
    output = args.output or default_output(config.bench)
    try:
        return compile_command(
            config=config,
            output=output,
            check=args.check,
            exclude_provisional=args.exclude_provisional,
        )
    except (BenchError, httpx.HTTPError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def compile_command(
    *, config: Config, output: Path, check: bool, exclude_provisional: bool = False
) -> int:
    """Read, validate, report; write MCF and codes.csv when passing and not --check.

    A failing run also deletes the MCF and codes.csv, so the output directory
    never holds artifacts that contradict the report beside them.

    Args:
        config: the bench to read.
        output: MCF output path; report.txt and codes.csv are written alongside it.
        check: when True, skip writing MCF and codes.csv even on a passing run.
        exclude_provisional: leave nodes flagged provisional out of the MCF and
            codes.csv.
    """
    graph = load_graph(config)
    result = validate.validate(graph, exclude_provisional=exclude_provisional)
    text = report.render(
        graph, result, config=config, exclude_provisional=exclude_provisional
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent / "report.txt").write_text(text)
    codes_path = output.parent / "codes.csv"

    if not result.ok:
        # Artifacts from an earlier, passing run would otherwise sit next to a
        # failure report and read as current.
        output.unlink(missing_ok=True)
        codes_path.unlink(missing_ok=True)
        sys.stderr.write(text)
        return 1
    if check:
        return 0
    written = provisional.without(graph) if exclude_provisional else graph
    output.write_text(emit.emit(written, config=config))
    codes_path.write_text(codes.render(written), encoding="utf-8")
    return 0


def load_graph(config: Config) -> Graph:
    """Read the named bench into a Graph.

    Args:
        config: the bench to read.
    """
    return reader.read(reader.fetch_entities(config=config), config=config)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser: one subcommand, `compile`, with its three flags."""
    parser = argparse.ArgumentParser(
        description="Compile the DFO concept store to Data Commons MCF."
    )
    subparsers = parser.add_subparsers(dest="command")
    compile_parser = subparsers.add_parser(
        "compile", help="Read the Wikibase bench, validate it, and write MCF."
    )
    # Required and defaultless: a run must say which bench it read, so no MCF or
    # report can come from a bench the author didn't name.
    compile_parser.add_argument(
        "--bench",
        required=True,
        choices=sorted(BENCHES),
        help="Which Wikibase instance to read.",
    )
    compile_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "MCF output path (default: output/<bench>/dfo.mcf). "
            "The run report and the code mapping are written alongside it "
            "as report.txt and codes.csv."
        ),
    )
    compile_parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and write the report without writing MCF.",
    )
    compile_parser.add_argument(
        "--exclude-provisional",
        action="store_true",
        help="Leave nodes flagged isProvisional out of the MCF and codes.csv.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
