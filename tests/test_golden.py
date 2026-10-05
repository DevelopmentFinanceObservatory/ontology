"""Golden test: a real bench compiles to a fixed MCF file and a fixed report.

The fixture is the `wbgetentities` payload set as returned by the API, captured
from the dfo-testing-2 bench on 2026-08-04 — production's vocabulary plus a
concept spine covering every shape the compiler emits. It runs the whole
pipeline, so any layer that changes the output changes this test.
"""

import json
from pathlib import Path

from dfo_ontology import codes, emit, reader, report, validate
from dfo_ontology.config import Config
from dfo_ontology.model import Graph, Result

FIXTURE = Path(__file__).parent / "fixtures" / "bench.json"
GOLDENS = Path(__file__).parent / "goldens"
CONFIG = Config(bench="testing")


def compiled() -> tuple[Graph, Result]:
    """Read the fixture into a graph and validate it."""
    graph = reader.read(json.loads(FIXTURE.read_text()), config=CONFIG)
    return graph, validate.validate(graph)


def test_bench_validates_clean() -> None:
    """No errors, one indeterminate skip on the individual, one orphan advisory."""
    _, result = compiled()
    assert result.errors == []
    assert [f.rule for f in result.skips] == ["S5|S6"]
    assert [f.rule for f in result.advisories] == ["A2"]


def test_bench_emits_golden_mcf() -> None:
    """Emission matches the committed MCF byte for byte."""
    graph, _ = compiled()
    assert emit.emit(graph, config=CONFIG) == (GOLDENS / "bench.mcf").read_text()


def test_bench_renders_golden_report() -> None:
    """The success report matches the committed text byte for byte."""
    graph, result = compiled()
    assert (
        report.render(graph, result, config=CONFIG)
        == (GOLDENS / "report.txt").read_text()
    )


def test_bench_renders_golden_codes_csv() -> None:
    """The codes.csv matches the committed file byte for byte.

    Header-only until the fixture is recaptured: this capture predates the
    classificationCode property on the bench.
    """
    graph, _ = compiled()
    assert codes.render(graph) == (GOLDENS / "bench.csv").read_text()
