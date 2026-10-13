"""Tests for cli.py. load_graph is monkeypatched; no test touches the network."""

from pathlib import Path

import pytest

from dfo_ontology import cli, codes, emit
from dfo_ontology.config import Config
from dfo_ontology.model import Kind
from dfo_ontology.reader import BenchError

from .graphbuild import bench_vocab, entity, graph, lit, ref

# A class and a property pointing at it: two nodes to emit, and the property's
# reference keeps A2 quiet. Vocabulary alone would emit nothing, which would let
# the MCF assertions below pass against an empty file.
CLEAN_GRAPH = graph(
    *bench_vocab(),
    entity(
        "Q10",
        id="SomeClass",
        label="some class",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    ),
    entity(
        "Q11",
        id="someProperty",
        label="some property",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q10")], "P7": [ref("Q10")]},
    ),
)
FAILING_GRAPH = graph(*bench_vocab(), entity("Q10", id="1bad", label="bad"))
DEV = Config(bench="dev")

# CLEAN_GRAPH plus a provisional subclass of SomeClass: the provisional node
# points at a settled one, never the other way, so excluding it passes E1.
PROVISIONAL_VOCAB = (
    entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional"),
    entity("Q30", dcid="schema:True"),
)
PROVISIONAL_GRAPH = graph(
    *CLEAN_GRAPH.entities.values(),
    *PROVISIONAL_VOCAB,
    entity(
        "Q12",
        id="DraftClass",
        label="draft class",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q10")], "P30": [ref("Q30")]},
    ),
)

# A minted classificationCode property, a value list, and one coded value:
# the smallest passing graph whose codes.csv carries a row.
CODED_GRAPH = graph(
    *bench_vocab(),
    entity(
        "P40",
        kind=Kind.PROPERTY,
        id="classificationCode",
        label="classification code",
        description="d",
        claims={"P6": [ref("Q3")], "P7": [ref("Q4")]},
    ),
    entity(
        "Q20",
        id="FruitEnum",
        label="fruit",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    ),
    entity(
        "Q21",
        id="Apple",
        label="apple",
        description="d",
        claims={"P3": [ref("Q20")], "P40": [lit("APL")]},
    ),
)


def test_compile_writes_mcf_and_report_on_success(tmp_path, monkeypatch) -> None:
    """A clean graph exits 0 and writes the emitter's MCF plus report.txt."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)
    output = tmp_path / "output" / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output)])

    assert exit_code == 0
    assert output.read_text() == emit.emit(CLEAN_GRAPH, config=DEV)
    assert (output.parent / "report.txt").exists()


def test_check_writes_report_but_not_mcf(tmp_path, monkeypatch) -> None:
    """--check validates and reports without writing MCF, still exit 0."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)
    output = tmp_path / "output" / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output), "--check"])

    assert exit_code == 0
    assert not output.exists()
    assert (output.parent / "report.txt").exists()


def test_failing_graph_reports_and_exits_1(tmp_path, monkeypatch, capsys) -> None:
    """A failing graph writes report.txt, skips MCF, exits 1, and mirrors stderr."""
    monkeypatch.setattr(cli, "load_graph", lambda config: FAILING_GRAPH)
    output = tmp_path / "output" / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output)])

    assert exit_code == 1
    assert not output.exists()
    report_text = (output.parent / "report.txt").read_text()
    assert capsys.readouterr().err == report_text


def test_failing_run_removes_an_mcf_left_by_an_earlier_run(
    tmp_path, monkeypatch
) -> None:
    """The MCF from a passing run does not survive a later failing one."""
    output = tmp_path / "output" / "dfo.mcf"
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)
    assert cli.main(["compile", "--bench", "dev", "-o", str(output)]) == 0
    assert output.exists()

    monkeypatch.setattr(cli, "load_graph", lambda config: FAILING_GRAPH)

    assert cli.main(["compile", "--bench", "dev", "-o", str(output)]) == 1
    assert not output.exists()


def test_output_flag_places_all_artifacts_alongside(tmp_path, monkeypatch) -> None:
    """-o other/place.mcf puts dfo.mcf, report.txt, and codes.csv in one directory."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)
    output = tmp_path / "other" / "place.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output)])

    assert exit_code == 0
    assert output.exists()
    assert (tmp_path / "other" / "report.txt").exists()
    assert (tmp_path / "other" / "codes.csv").exists()


def test_compile_writes_codes_csv_on_success(tmp_path, monkeypatch) -> None:
    """A passing run writes codes.csv byte-equal to the renderer's output."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CODED_GRAPH)
    output = tmp_path / "output" / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output)])

    assert exit_code == 0
    written = (output.parent / "codes.csv").read_text(encoding="utf-8")
    assert written == codes.render(CODED_GRAPH)
    assert "dcid:Apple" in written


def test_check_does_not_write_codes_csv(tmp_path, monkeypatch) -> None:
    """--check skips codes.csv exactly as it skips the MCF."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CODED_GRAPH)
    output = tmp_path / "output" / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output), "--check"])

    assert exit_code == 0
    assert not (output.parent / "codes.csv").exists()


def test_failing_run_removes_codes_csv_left_by_an_earlier_run(
    tmp_path, monkeypatch
) -> None:
    """The codes.csv from a passing run does not survive a later failing one."""
    output = tmp_path / "output" / "dfo.mcf"
    monkeypatch.setattr(cli, "load_graph", lambda config: CODED_GRAPH)
    assert cli.main(["compile", "--bench", "dev", "-o", str(output)]) == 0
    assert (output.parent / "codes.csv").exists()

    monkeypatch.setattr(cli, "load_graph", lambda config: FAILING_GRAPH)

    assert cli.main(["compile", "--bench", "dev", "-o", str(output)]) == 1
    assert not (output.parent / "codes.csv").exists()


def test_bench_error_exits_2(monkeypatch, capsys) -> None:
    """A BenchError from load_graph exits 2 with one stderr line."""

    def raise_bench_error(config) -> None:
        raise BenchError("bad-token: something went wrong")

    monkeypatch.setattr(cli, "load_graph", raise_bench_error)

    exit_code = cli.main(["compile", "--bench", "dev"])

    assert exit_code == 2
    err_lines = capsys.readouterr().err.splitlines()
    assert len(err_lines) == 1


def test_oserror_on_write_exits_2(tmp_path, monkeypatch) -> None:
    """An OSError writing the artifacts (e.g. a blocked path) exits 2."""
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    output = blocked / "dfo.mcf"

    exit_code = cli.main(["compile", "--bench", "dev", "-o", str(output)])

    assert exit_code == 2


def test_main_with_no_subcommand_shows_usage(capsys) -> None:
    """main([]) with no subcommand prints usage and exits non-zero."""
    exit_code = cli.main([])

    assert exit_code != 0
    assert "usage" in capsys.readouterr().err.lower()


# --- Bench selection ---------------------------------------------------------


def test_compile_without_bench_is_a_usage_error(capsys) -> None:
    """No default bench: a compile that names none exits 2 rather than reading one."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["compile"])

    assert exit_info.value.code == 2
    assert "--bench" in capsys.readouterr().err


def test_unknown_bench_is_a_usage_error(capsys) -> None:
    """A misspelled bench exits 2 and lists the names that exist."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["compile", "--bench", "prodd"])

    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "prod" in err and "dev" in err


def test_bench_reaches_load_graph_and_both_artifacts(tmp_path, monkeypatch) -> None:
    """The named bench is the one read, and the one both artifacts record."""
    seen: list[Config] = []

    def record(config: Config):
        seen.append(config)
        return CLEAN_GRAPH

    monkeypatch.setattr(cli, "load_graph", record)
    output = tmp_path / "dfo.mcf"

    assert cli.main(["compile", "--bench", "prod", "-o", str(output)]) == 0

    assert [c.bench for c in seen] == ["prod"]
    assert output.read_text().startswith("# bench: prod (")
    assert (tmp_path / "report.txt").read_text().startswith("bench: prod (")


def test_each_bench_gets_its_own_default_output_directory(monkeypatch) -> None:
    """Compiling one bench cannot overwrite another's MCF."""
    assert cli.default_output("prod") == Path("output/prod/dfo.mcf")
    assert cli.default_output("dev") == Path("output/dev/dfo.mcf")


def test_default_output_is_used_when_no_output_flag(tmp_path, monkeypatch) -> None:
    """Without -o, the artifacts land under output/<bench>/."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_graph", lambda config: CLEAN_GRAPH)

    assert cli.main(["compile", "--bench", "dev"]) == 0

    assert (tmp_path / "output" / "dev" / "dfo.mcf").exists()
    assert (tmp_path / "output" / "dev" / "report.txt").exists()


def test_provisional_nodes_are_emitted_by_default(tmp_path, monkeypatch) -> None:
    """Without the option the provisional node is in the MCF and the report."""
    monkeypatch.setattr(cli, "load_graph", lambda config: PROVISIONAL_GRAPH)
    output = tmp_path / "dfo.mcf"

    assert cli.main(["compile", "--bench", "dev", "-o", str(output)]) == 0
    assert "Node: dcid:DraftClass\n" in output.read_text()
    report_text = (tmp_path / "report.txt").read_text()
    assert "Provisional (1), included in the MCF and codes.csv" in report_text


def test_exclude_provisional_leaves_them_out(tmp_path, monkeypatch) -> None:
    """--exclude-provisional writes the MCF without them and says so."""
    monkeypatch.setattr(cli, "load_graph", lambda config: PROVISIONAL_GRAPH)
    output = tmp_path / "dfo.mcf"

    argv = ["compile", "--bench", "dev", "-o", str(output), "--exclude-provisional"]
    assert cli.main(argv) == 0
    mcf = output.read_text()
    assert "Node: dcid:DraftClass\n" not in mcf
    assert "Node: dcid:SomeClass\n" in mcf
    report_text = (tmp_path / "report.txt").read_text()
    assert "Provisional (1), left out of the MCF and codes.csv" in report_text


def test_exclude_provisional_fails_when_a_settled_node_depends_on_one(
    tmp_path, monkeypatch
) -> None:
    """A settled property ranging over a provisional class fails E1, no MCF."""
    flagged_class = entity(
        "Q10",
        id="SomeClass",
        label="some class",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")], "P30": [ref("Q30")]},
    )
    others = [e for e in CLEAN_GRAPH.entities.values() if e.qid != "Q10"]
    g = graph(*others, *PROVISIONAL_VOCAB, flagged_class)
    monkeypatch.setattr(cli, "load_graph", lambda config: g)
    output = tmp_path / "dfo.mcf"

    argv = ["compile", "--bench", "dev", "-o", str(output), "--exclude-provisional"]
    assert cli.main(argv) == 1
    assert not output.exists()
    assert "E1" in (tmp_path / "report.txt").read_text()
