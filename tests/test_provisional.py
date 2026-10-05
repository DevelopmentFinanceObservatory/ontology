"""Tests for provisional.py."""

from dfo_ontology import provisional, validate
from dfo_ontology.model import Entity, Kind

from .graphbuild import bench_vocab, entity, graph, lit, ref

FLAG = entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional")
TRUE = entity("Q30", dcid="schema:True")
FALSE = entity("Q31", dcid="schema:False")
A_CLASS = entity(
    "Q10", id="SomeClass", label="c", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
)


def node(qid: str, id: str, *flags: str) -> Entity:
    """An individual of SomeClass, flagged through isProvisional at each target."""
    return entity(
        qid,
        id=id,
        label=id.lower(),
        claims={"P3": [ref("Q10")], "P30": [ref(f) for f in flags]},
    )


def test_flag_to_true_is_provisional() -> None:
    """isProvisional → True marks the node."""
    g = graph(*bench_vocab(), FLAG, TRUE, A_CLASS, node("Q11", "Flagged", "Q30"))
    assert provisional.is_provisional(g, g.entities["Q11"])


def test_unflagged_and_false_are_not_provisional() -> None:
    """No flag, or a flag to False, leaves the node final."""
    g = graph(
        *bench_vocab(),
        FLAG,
        TRUE,
        FALSE,
        A_CLASS,
        node("Q11", "Plain"),
        node("Q12", "Settled", "Q31"),
    )
    assert not provisional.is_provisional(g, g.entities["Q11"])
    assert not provisional.is_provisional(g, g.entities["Q12"])


def test_nothing_is_provisional_without_the_property() -> None:
    """A bench that has not minted isProvisional has no provisional nodes."""
    g = graph(*bench_vocab(), A_CLASS, node("Q11", "Plain"))
    assert provisional.flagged(g) == []


def test_flagged_lists_flagged_nodes_by_id() -> None:
    """Only flagged id-carrying nodes, sorted by id."""
    g = graph(
        *bench_vocab(),
        FLAG,
        TRUE,
        A_CLASS,
        node("Q11", "Zebra", "Q30"),
        node("Q12", "Apple", "Q30"),
        node("Q13", "Mango"),
    )
    assert [e.id for e in provisional.flagged(g)] == ["Apple", "Zebra"]


def test_without_takes_out_only_the_flagged_nodes() -> None:
    """Everything but the flagged nodes survives, references and reader findings too."""
    g = graph(
        *bench_vocab(),
        FLAG,
        TRUE,
        A_CLASS,
        node("Q11", "Draft", "Q30"),
        node("Q12", "Settled"),
    )
    kept = provisional.without(g)
    assert set(g.entities) - set(kept.entities) == {"Q11"}
    assert kept.findings == g.findings
    assert kept.entity_by_id("Settled") is g.entities["Q12"]


# --- E1 -------------------------------------------------------------------------

DRAFT_ENUM = entity(
    "Q20",
    id="DraftEnum",
    label="draft",
    description="d",
    claims={"P3": [ref("Q1")], "P4": [ref("Q3")], "P30": [ref("Q30")]},
)
DRAFT_PROP = entity(
    "P31",
    kind=Kind.PROPERTY,
    id="draftProperty",
    label="draft property",
    description="d",
    claims={"P6": [ref("Q10")], "P7": [ref("Q20")], "P30": [ref("Q30")]},
)


def test_e1_names_a_settled_node_pointing_at_a_provisional_one() -> None:
    """A settled value typed by a provisional list would emit a dangling typeOf."""
    value = entity("Q21", id="Settled", label="s", claims={"P3": [ref("Q20")]})
    g = graph(*bench_vocab(), FLAG, TRUE, DRAFT_ENUM, value)
    findings = provisional.exclusion_findings(g)
    assert [(f.rule, f.entity.id, f.value) for f in findings] == [
        ("E1", "Settled", "DraftEnum")
    ]


def test_e1_names_a_settled_node_stated_through_a_provisional_property() -> None:
    """One finding per provisional property, however many times it is stated."""
    individual = entity(
        "Q11",
        id="Settled",
        label="s",
        claims={"P3": [ref("Q10")], "P31": [ref("Q10"), ref("Q10")]},
    )
    g = graph(*bench_vocab(), FLAG, TRUE, A_CLASS, DRAFT_ENUM, DRAFT_PROP, individual)
    findings = provisional.exclusion_findings(g)
    assert [(f.entity.id, f.predicate, f.value) for f in findings] == [
        ("Settled", "draftProperty", None)
    ]


def test_e1_ignores_provisional_nodes_and_settled_targets() -> None:
    """Provisional to provisional, or provisional to settled, leaves nothing out."""
    g = graph(*bench_vocab(), FLAG, TRUE, A_CLASS, DRAFT_ENUM, DRAFT_PROP)
    assert provisional.exclusion_findings(g) == []


def test_validate_runs_e1_only_when_excluding() -> None:
    """E1 is an error with exclusion and absent without it."""
    value = entity(
        "Q21", id="Settled", label="s", description="d", claims={"P3": [ref("Q20")]}
    )
    g = graph(*bench_vocab(), FLAG, TRUE, DRAFT_ENUM, value)
    assert not any(f.rule == "E1" for f in validate.validate(g).errors)
    assert any(
        f.rule == "E1" for f in validate.validate(g, exclude_provisional=True).errors
    )


def test_e1_names_a_coded_reference_typed_by_a_provisional_class() -> None:
    """A coded reference's codes.csv row names its class; an uncoded one has no row."""
    dac = entity("P40", kind=Kind.PROPERTY, id="dacCode")
    draft_class = entity(
        "Q22",
        id="DraftClass",
        label="draft class",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")], "P30": [ref("Q30")]},
    )
    coded = entity(
        "Q23", dcid="country/AUT", claims={"P3": [ref("Q22")], "P40": [lit("1")]}
    )
    uncoded = entity("Q24", dcid="country/BEL", claims={"P3": [ref("Q22")]})
    g = graph(*bench_vocab(), FLAG, TRUE, dac, draft_class, coded, uncoded)
    findings = provisional.exclusion_findings(g)
    assert [(f.entity.dcid, f.value) for f in findings] == [
        ("country/AUT", "DraftClass")
    ]
