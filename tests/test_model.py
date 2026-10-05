"""Tests for model.py."""

from dfo_ontology.model import Kind, escape

from .graphbuild import bench_vocab, entity, graph, ref


def test_build_sorts_entities_by_qid() -> None:
    """Graph.entities is keyed in sorted-qid order regardless of input order."""
    g = graph(entity("Q2", id="Bar"), entity("Q1", id="Foo"))
    assert list(g.entities) == ["Q1", "Q2"]


def test_build_is_deterministic_across_permutations() -> None:
    """Two permutations of the same entities produce identical indexes."""
    entities = [
        entity("Q3", id="Baz"),
        entity("Q1", id="Foo", claims={"P6": [ref("Q3")]}),
        entity("Q2", id="Bar"),
    ]
    forward = graph(*entities)
    backward = graph(*reversed(entities))
    assert forward.entities.keys() == backward.entities.keys()
    assert forward.by_id == backward.by_id
    assert forward.by_dcid == backward.by_dcid
    assert forward.predicate_names == backward.predicate_names
    assert forward.properties_by_name == backward.properties_by_name


def test_duplicate_id_lands_as_multi_claimant_list() -> None:
    """Two entities claiming the same id both appear in by_id, sorted by qid."""
    g = graph(entity("Q2", id="Foo"), entity("Q1", id="Foo"))
    assert g.by_id["Foo"] == ["Q1", "Q2"]
    assert g.entity_by_id("Foo") is g.entities["Q1"]


def test_duplicate_dcid_lands_as_multi_claimant_list() -> None:
    """Two entities claiming the same dcid both appear in by_dcid, sorted by qid."""
    g = graph(entity("Q2", dcid="schema:Foo"), entity("Q1", dcid="schema:Foo"))
    assert g.by_dcid["schema:Foo"] == ["Q1", "Q2"]
    assert g.entity_by_dcid("schema:Foo") is g.entities["Q1"]


def test_entity_by_id_and_dcid_absent() -> None:
    """A lookup that matches nothing returns None."""
    g = graph(*bench_vocab())
    assert g.entity_by_id("Nope") is None
    assert g.entity_by_dcid("schema:Nope") is None


def test_statements_excludes_bookkeeping_and_preserves_order() -> None:
    """statements() drops id/dcid claims and keeps authored order."""
    e = entity(
        "Q10",
        kind=Kind.ITEM,
        id="FinancingActivity",
        claims={"P6": [ref("Q11")], "P7": [ref("Q12"), ref("Q13")]},
    )
    g = graph(*bench_vocab(), e)
    statements = g.statements(e)
    assert [(s.predicate, s.value) for s in statements] == [
        ("domainIncludes", ref("Q11")),
        ("rangeIncludes", ref("Q12")),
        ("rangeIncludes", ref("Q13")),
    ]


def test_values_and_resolved_present_target() -> None:
    """values()/resolved() return the stated value and its resolved target."""
    target = entity("Q11", id="FinancingPurposeEnum")
    e = entity("Q10", id="FinancingActivity", claims={"P6": [ref("Q11")]})
    g = graph(*bench_vocab(), target, e)
    assert g.values(e, "domainIncludes") == [ref("Q11")]
    resolved = list(g.resolved(e, "domainIncludes"))
    assert resolved == [(ref("Q11"), target)]


def test_values_and_resolved_absent_target() -> None:
    """resolved() yields nothing for a dangling target; values() still reports it."""
    e = entity("Q10", id="FinancingActivity", claims={"P6": [ref("Q999")]})
    g = graph(*bench_vocab(), e)
    assert g.values(e, "domainIncludes") == [ref("Q999")]
    assert list(g.resolved(e, "domainIncludes")) == []


def test_dangling() -> None:
    """dangling() names the predicate and ref of every unresolvable statement."""
    e = entity(
        "Q10",
        id="FinancingActivity",
        claims={"P6": [ref("Q999")], "P7": [ref("Q1")]},
    )
    g = graph(*bench_vocab(), e)
    assert g.dangling(e) == [("domainIncludes", ref("Q999"))]


def test_emitted_predicate_dcid_property() -> None:
    """A dcid-carrying property emits its bare dcid name."""
    g = graph(*bench_vocab())
    assert g.emitted_predicate("P6") == "domainIncludes"


def test_emitted_predicate_minted_property() -> None:
    """An id-carrying property emits its bare id — predicate names carry no
    namespace prefix."""
    minted = entity("P9", kind=Kind.PROPERTY, id="financingPurpose")
    g = graph(*bench_vocab(), minted)
    assert g.emitted_predicate("P9") == "financingPurpose"


def test_predicate_label_known_and_passthrough() -> None:
    """predicate_label resolves a known property qid, else passes the key through."""
    g = graph(*bench_vocab())
    assert g.predicate_label("P6") == "domainIncludes"
    assert g.predicate_label("not-a-qid") == "not-a-qid"


def test_defined_and_references() -> None:
    """defined() and references() filter and sort by id / dcid respectively."""
    g = graph(entity("Q10", id="Zeta"), entity("Q11", id="Alpha"))
    assert [e.id for e in g.defined()] == ["Alpha", "Zeta"]

    g = graph(
        entity("Q1", dcid="schema:Thing"),
        entity("Q2", dcid="schema:Class"),
    )
    assert [e.dcid for e in g.references()] == ["schema:Class", "schema:Thing"]


def test_escape() -> None:
    """escape() backslash-escapes double quotes and nothing else."""
    assert escape('say "hi"') == 'say \\"hi\\"'
    assert escape("plain") == "plain"
