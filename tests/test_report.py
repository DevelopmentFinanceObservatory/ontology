"""Tests for report.py. Result objects are built directly; no validator run."""

from dfo_ontology import report
from dfo_ontology.config import Config
from dfo_ontology.model import Finding, Kind, Result

from .graphbuild import bench_vocab, entity, graph, lit, ref

CONFIG = Config(bench="testing")
PREAMBLE = "bench: testing (https://dfo-testing-2.wikibase.cloud)\n\n"

# --- Header ------------------------------------------------------------


def test_header_singular() -> None:
    """One error naming one entity reads "1 error across 1 entity"."""
    e = entity("Q10", id="Foo")
    result = Result(errors=[Finding("I4", entity=e, message="bad id")])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    assert text.startswith("1 error across 1 entity\n")


def test_header_plural() -> None:
    """Two errors naming two entities read "2 errors across 2 entities"."""
    a = entity("Q10", id="Foo")
    b = entity("Q11", id="Bar")
    result = Result(
        errors=[
            Finding("I4", entity=a, message="bad id"),
            Finding("I10", entity=b, message="has no English label"),
        ]
    )
    text = report.failure_report(graph(*bench_vocab(), a, b), result)
    assert text.startswith("2 errors across 2 entities\n")


def test_header_mixed_per_entity_and_cross_entity() -> None:
    """A mix of per-entity and cross-entity errors states both counts, not just one."""
    a = entity("Q10", id="Foo")
    result = Result(
        errors=[
            Finding("I4", entity=a, message="bad id"),
            Finding("I5", value='duplicate id "Foo"', message="Q10, Q11"),
        ]
    )
    text = report.failure_report(graph(*bench_vocab(), a), result)
    assert text.startswith("2 errors: 1 across 1 entity, 1 cross-entity\n")


def test_header_cross_entity_only() -> None:
    """Errors that are all cross-entity never claim zero entities in the header."""
    result = Result(
        errors=[
            Finding("I5", value='duplicate id "Foo"', message="Q10, Q11"),
            Finding("G8", value="subClassOf cycle", message="Bar, Baz"),
        ]
    )
    text = report.failure_report(graph(*bench_vocab()), result)
    assert text.startswith("2 errors, all cross-entity\n")
    assert "0 entities" not in text


# --- Group ordering ------------------------------------------------------


def test_group_ordering_by_total_key() -> None:
    """id-carrying, then dcid-carrying, then identifier-less, qid numeric within a bucket."""
    id_entity = entity("Q20", id="Zeta")
    dcid_entity = entity("Q21", dcid="schema:Alpha")
    none_low = entity("Q9")
    none_high = entity("Q10")
    result = Result(
        errors=[
            Finding("I1", entity=id_entity, message="m"),
            Finding("I1", entity=dcid_entity, message="m"),
            Finding("I1", entity=none_low, message="m"),
            Finding("I1", entity=none_high, message="m"),
        ]
    )
    g = graph(*bench_vocab(), id_entity, dcid_entity, none_low, none_high)
    text = report.failure_report(g, result)
    headers = [line for line in text.splitlines() if not line.startswith("  ")]
    order = [h for h in headers if h and "error" not in h and h != report.FOOTER]
    assert order == [
        report.entity_header(id_entity),
        report.entity_header(dcid_entity),
        report.entity_header(none_low),
        report.entity_header(none_high),
    ]


# --- Within-group ordering -------------------------------------------------


def test_within_group_ordering() -> None:
    """Findings within a group sort by (rule, predicate, value)."""
    e = entity("Q10", id="Foo")
    result = Result(
        errors=[
            Finding("G4", entity=e, predicate="rangeIncludes", value="b", message="m"),
            Finding("G3", entity=e, predicate="domainIncludes", value="a", message="m"),
            Finding("G4", entity=e, predicate="rangeIncludes", value="a", message="m"),
        ]
    )
    text = report.failure_report(graph(*bench_vocab(), e), result)
    lines = [line for line in text.splitlines() if line.startswith("  ")]
    assert lines == [
        "  G3  domainIncludes → a: m",
        "  G4  rangeIncludes → a: m",
        "  G4  rangeIncludes → b: m",
    ]


# --- Cross-entity section -------------------------------------------------


def test_cross_entity_section() -> None:
    """Findings with no entity land in their own section, sorted by (rule, message, value)."""
    result = Result(
        errors=[
            Finding("I5", value='duplicate id "Foo"', message="Q10, Q11"),
            Finding("G8", value="subClassOf cycle", message="Bar, Baz"),
        ]
    )
    text = report.failure_report(graph(*bench_vocab()), result)
    assert "Cross-entity" in text
    lines = text.splitlines()
    idx = lines.index("Cross-entity")
    # Sorted by (rule, message, value): G8's message "Bar, Baz" precedes I5's rule anyway.
    assert lines[idx + 1] == "  G8  subClassOf cycle: Bar, Baz"
    assert lines[idx + 2] == '  I5  duplicate id "Foo": Q10, Q11'


# --- Finding-line degradations ---------------------------------------------


def test_finding_line_predicate_and_value() -> None:
    """predicate → value: message, when both are present."""
    e = entity("Q10", id="Foo")
    finding = Finding(
        "G7",
        entity=e,
        predicate="specializationOf",
        value="dcid:X",
        message="not a value in the same list",
    )
    result = Result(errors=[finding])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    assert "  G7  specializationOf → dcid:X: not a value in the same list" in text


def test_finding_line_predicate_only() -> None:
    """predicate: message, when value is absent."""
    e = entity("Q10", id="Foo")
    finding = Finding("I2", entity=e, predicate="id", message="stated 2 times")
    result = Result(errors=[finding])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    assert "  I2  id: stated 2 times" in text


def test_finding_line_value_only() -> None:
    """value: message, when predicate is absent."""
    e = entity("Q10", id="Foo")
    finding = Finding("I4", entity=e, value='id "basic-health"', message="bad syntax")
    result = Result(errors=[finding])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    assert '  I4  id "basic-health": bad syntax' in text


def test_finding_line_message_only() -> None:
    """Bare message, when neither predicate nor value is present."""
    e = entity("Q10", id="Foo")
    finding = Finding("I1", entity=e, message="carries neither id nor dcid")
    result = Result(errors=[finding])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    assert "  I1  carries neither id nor dcid" in text


# --- Predicate rendering ---------------------------------------------------


def test_reader_finding_predicate_qid_renders_as_predicate_name() -> None:
    """A reader finding's property qid renders through graph.predicate_label."""
    prop = entity("P9", kind=Kind.PROPERTY, id="financingPurpose")
    e = entity("Q10", id="Foo")
    finding = Finding("R1", entity=e, predicate="P9", value="x", message="dropped")
    result = Result(errors=[finding])
    text = report.failure_report(graph(*bench_vocab(), prop, e), result)
    assert "  R1  financingPurpose → x: dropped" in text


# --- Not run ----------------------------------------------------------------


def test_not_run_line() -> None:
    """A single Not run line, rule ids sorted, right after the header."""
    result = Result(not_run=frozenset({"S4", "G2", "S1"}))
    text = report.failure_report(graph(*bench_vocab()), result)
    lines = text.splitlines()
    assert lines[0].startswith("0 error")
    assert lines[1] == "Not run: G2, S1, S4"


def test_not_run_absent_when_empty() -> None:
    """No Not run line at all when nothing is blocked."""
    result = Result()
    text = report.failure_report(graph(*bench_vocab()), result)
    assert "Not run" not in text


def test_not_run_sorts_naturally_not_lexicographically() -> None:
    """Rule ids sort by letter prefix then numeric suffix, so I2 precedes I10."""
    result = Result(not_run=frozenset({"I2", "I10", "G5", "S7", "A1"}))
    text = report.failure_report(graph(*bench_vocab()), result)
    lines = text.splitlines()
    assert lines[1] == "Not run: A1, G5, I2, I10, S7"


# --- Skip section ------------------------------------------------------------


def test_skip_section() -> None:
    """A skip names its entity in full and degrades like any other finding."""
    e = entity("Q12", id="CRSPurposeBasicHealth", label="basic health (CRS purpose)")
    finding = Finding(
        "G4",
        entity=e,
        predicate="rangeIncludes",
        value="schema:Text",
        message="target carries no local typing",
    )
    result = Result(skips=[finding])
    text = report.failure_report(graph(*bench_vocab(), e), result)
    expected = (
        '  G4  CRSPurposeBasicHealth — "basic health (CRS purpose)" (Q12)  '
        "rangeIncludes → schema:Text: target carries no local typing"
    )
    assert "Skipped checks" in text
    assert expected in text


def test_skip_section_absent_when_empty() -> None:
    """No Skipped checks section printed when there are no skips."""
    text = report.failure_report(graph(*bench_vocab()), Result())
    assert "Skipped checks" not in text


# --- Success form ------------------------------------------------------------


def test_success_zero_counts_on_bench_vocab_alone() -> None:
    """The live bench's own vocabulary emits zero nodes and ten references."""
    text = report.success_report(graph(*bench_vocab()), Result())
    assert text == (
        "0 class, 0 property, 0 value list, 0 value, 0 individual\n"
        "10 reference entities emitted no node\n"
    )


def test_success_counts_by_shape() -> None:
    """Each of class, property, value list, value, and individual is counted."""
    some_class = entity(
        "Q10",
        id="SomeClass",
        label="c",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    foo_enum = entity(
        "Q11",
        id="FooEnum",
        label="e",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    minted_prop = entity(
        "P9", kind=Kind.PROPERTY, id="mintedProp", label="p", description="d"
    )
    constraint_prop = entity(
        "P10",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="p",
        description="d",
        claims={"P3": [ref("Q2")]},
    )
    some_value = entity(
        "Q12", id="SomeValue", label="v", description="d", claims={"P3": [ref("Q11")]}
    )
    some_individual = entity(
        "Q13",
        id="SomeIndividual",
        label="i",
        description="d",
        claims={"P3": [ref("Q10")]},
    )
    g = graph(
        *bench_vocab(),
        some_class,
        foo_enum,
        minted_prop,
        constraint_prop,
        some_value,
        some_individual,
    )
    text = report.success_report(g, Result())
    assert text.startswith("1 class, 2 property, 1 value list, 1 value, 1 individual\n")
    assert "10 reference entities emitted no node" in text


def test_success_indeterminate_count() -> None:
    """A blind typeOf-target subClassOf chain dispatches S5|S6, counted separately."""
    blind_ref = entity("Q20", dcid="schema:SomeRef")
    blind_target = entity(
        "Q21",
        id="BlindTarget",
        label="b",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q20")]},
    )
    indeterminate = entity(
        "Q22",
        id="SomeIndeterminate",
        label="x",
        description="d",
        claims={"P3": [ref("Q21")]},
    )
    g = graph(*bench_vocab(), blind_ref, blind_target, indeterminate)
    text = report.success_report(g, Result())
    assert text.startswith(
        "1 class, 0 property, 0 value list, 0 value, 0 individual, 1 indeterminate\n"
    )
    assert "11 reference entities emitted no node" in text


def test_success_with_skip_and_advisory_sections() -> None:
    """A1/A2 advisories and skips print on an otherwise-successful report."""
    no_description = entity("Q10", id="Foo", label="A")
    orphan = entity("Q11", id="Bar", label="B", description="d")
    result = Result(
        advisories=[
            Finding("A1", entity=no_description, message="no English description"),
            Finding(
                "A2",
                entity=orphan,
                message="orphan — nothing on the bench points at it",
            ),
        ],
    )
    text = report.success_report(graph(*bench_vocab(), no_description, orphan), result)
    assert "Advisories" in text
    assert (
        f"  A1  {report.entity_header(no_description)}: no English description" in text
    )
    assert (
        f"  A2  {report.entity_header(orphan)}: "
        "orphan — nothing on the bench points at it" in text
    )
    assert text.rstrip("\n").endswith(report.FOOTER)


def test_success_without_skip_or_advisory_has_no_footer() -> None:
    """The footer is omitted from a clean success report with nothing to flag."""
    text = report.success_report(graph(*bench_vocab()), Result())
    assert report.FOOTER not in text


# --- Codes section -------------------------------------------------------------

CODE_PROP = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
FRUIT_ENUM = entity(
    "Q90",
    id="FruitEnum",
    label="fruit",
    description="d",
    claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
)
APPLE = entity(
    "Q91",
    id="Apple",
    label="apple",
    description="d",
    claims={"P3": [ref("Q90")], "P40": [lit("APL")]},
)


def test_success_names_a_fully_coded_list() -> None:
    """Every value coded reads "n of n", with no uncoded line."""
    text = report.success_report(
        graph(*bench_vocab(), CODE_PROP, FRUIT_ENUM, APPLE), Result()
    )
    assert 'Codes\n  FruitEnum — "fruit" (Q90): 1 of 1 coded' in text
    assert "uncoded" not in text


def test_success_names_uncoded_values_in_a_partially_coded_list() -> None:
    """A coded list with gaps counts them and names each uncoded value."""
    banana = entity(
        "Q92",
        id="Banana",
        label="banana",
        description="d",
        claims={"P3": [ref("Q90")]},
    )
    text = report.success_report(
        graph(*bench_vocab(), CODE_PROP, FRUIT_ENUM, APPLE, banana), Result()
    )
    assert '  FruitEnum — "fruit" (Q90): 1 of 2 coded' in text
    assert '    uncoded: Banana — "banana" (Q92)' in text


def test_success_has_no_codes_section_without_codes() -> None:
    """A graph without any coded entity renders no section."""
    text = report.success_report(graph(*bench_vocab(), FRUIT_ENUM), Result())
    assert "Codes" not in text


def test_success_counts_daccode_coverage_on_individuals() -> None:
    """Individuals coded through dacCode get the same coverage line as values."""
    dac_prop = entity("P41", kind=Kind.PROPERTY, id="dacCode")
    a_class = entity(
        "Q93",
        id="SomeClass",
        label="some class",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    coded = entity(
        "Q94",
        id="SomeOrg",
        label="some org",
        description="d",
        claims={"P3": [ref("Q93")], "P41": [lit("913")]},
    )
    uncoded = entity(
        "Q95",
        id="OtherOrg",
        label="other org",
        description="d",
        claims={"P3": [ref("Q93")]},
    )
    text = report.success_report(
        graph(*bench_vocab(), dac_prop, a_class, coded, uncoded), Result()
    )
    assert '  SomeClass — "some class" (Q93): 1 of 2 coded' in text
    assert '    uncoded: OtherOrg — "other org" (Q95)' in text


def test_codes_section_does_not_force_the_footer() -> None:
    """The coverage section carries no rule ids, so it never brings the footer."""
    text = report.success_report(
        graph(*bench_vocab(), CODE_PROP, FRUIT_ENUM, APPLE), Result()
    )
    assert report.FOOTER not in text


def test_failure_report_has_no_codes_section() -> None:
    """The failure form stays focused on errors."""
    result = Result(errors=[Finding("I4", entity=APPLE, message="bad id")])
    text = report.failure_report(
        graph(*bench_vocab(), CODE_PROP, FRUIT_ENUM, APPLE), result
    )
    assert "Codes" not in text


# --- Provisional section --------------------------------------------------------

FLAG = entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional")
TRUE = entity("Q30", dcid="schema:True")
FLAGGED_APPLE = entity(
    "Q91",
    id="Apple",
    label="apple",
    description="d",
    claims={"P3": [ref("Q90")], "P30": [ref("Q30")]},
)


def test_success_lists_provisional_nodes() -> None:
    """Each provisional node is named in full under a counted heading."""
    text = report.success_report(
        graph(*bench_vocab(), FLAG, TRUE, FRUIT_ENUM, FLAGGED_APPLE), Result()
    )
    assert (
        'Provisional (1), included in the MCF and codes.csv\n  Apple — "apple" (Q91)\n'
        in text
    )


def test_success_says_when_provisional_nodes_were_left_out() -> None:
    """With exclusion, the heading says the nodes are not in the artifacts."""
    text = report.success_report(
        graph(*bench_vocab(), FLAG, TRUE, FRUIT_ENUM, FLAGGED_APPLE),
        Result(),
        exclude_provisional=True,
    )
    assert "Provisional (1), left out of the MCF and codes.csv\n" in text


def test_success_has_no_provisional_section_without_flags() -> None:
    """A graph with nothing flagged renders no section."""
    text = report.success_report(
        graph(*bench_vocab(), FLAG, TRUE, FRUIT_ENUM, APPLE), Result()
    )
    assert "Provisional" not in text


def test_provisional_section_does_not_force_the_footer() -> None:
    """The section carries no rule ids, so it never brings the footer."""
    text = report.success_report(
        graph(*bench_vocab(), FLAG, TRUE, FRUIT_ENUM, FLAGGED_APPLE), Result()
    )
    assert report.FOOTER not in text


def test_failure_report_has_no_provisional_section() -> None:
    """The failure form stays focused on errors."""
    result = Result(errors=[Finding("I4", entity=FLAGGED_APPLE, message="bad id")])
    text = report.failure_report(
        graph(*bench_vocab(), FLAG, TRUE, FRUIT_ENUM, FLAGGED_APPLE), result
    )
    assert "Provisional" not in text


# --- render() dispatch -------------------------------------------------------


def test_render_dispatches_on_ok() -> None:
    """render() picks the success form when result.ok, else the failure form."""
    g = graph(*bench_vocab())
    assert report.render(
        g, Result(), config=CONFIG
    ) == PREAMBLE + report.success_report(g, Result())
    e = entity("Q10", id="Foo")
    failing = Result(errors=[Finding("I4", entity=e, message="bad")])
    g2 = graph(*bench_vocab(), e)
    assert report.render(
        g2, failing, config=CONFIG
    ) == PREAMBLE + report.failure_report(g2, failing)


def test_render_names_the_bench_on_the_first_line() -> None:
    """The first line is the bench and its browsable URL, then a blank line."""
    text = report.render(graph(*bench_vocab()), Result(), config=Config(bench="prod"))
    first, blank, _ = text.split("\n", 2)
    assert first == "bench: prod (https://developmentfinance.wikibase.cloud)"
    assert blank == ""
    assert "api.php" not in text


# --- Trailing newline ---------------------------------------------------------


def test_both_forms_end_in_exactly_one_newline() -> None:
    """Neither form ends in a blank line or is missing its trailing newline."""
    success_text = report.success_report(graph(*bench_vocab()), Result())
    assert success_text.endswith("\n") and not success_text.endswith("\n\n")

    e = entity("Q10", id="Foo")
    failing = Result(errors=[Finding("I4", entity=e, message="bad")])
    failure_text = report.failure_report(graph(*bench_vocab(), e), failing)
    assert failure_text.endswith("\n") and not failure_text.endswith("\n\n")
