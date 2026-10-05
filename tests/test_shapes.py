"""Tests for shapes.py."""

from dfo_ontology import shapes
from dfo_ontology.model import Kind
from dfo_ontology.shapes import Dispatch, Reach, Shape

from .graphbuild import bench_vocab, entity, graph, lit, ref


def test_bare_strips_to_last_colon() -> None:
    """schema:, dcs:, and dcid: prefixes are equivalent; no colon passes through."""
    assert shapes.bare("schema:Class") == "Class"
    assert shapes.bare("dcs:Class") == "Class"
    assert shapes.bare("dcid:Class") == "Class"
    assert shapes.bare("Class") == "Class"


def test_claimants_ambiguity() -> None:
    """Two items claiming the same bare dcid both appear, in qid order."""
    g = graph(*bench_vocab(), entity("Q99", dcid="schema:Class"))
    found = shapes.claimants(g, "Class")
    assert [e.qid for e in found] == ["Q1", "Q99"]
    assert shapes.well_known(g, "Class") is g.entities["Q1"]


def test_is_class_true() -> None:
    """An entity typed Class dispatches is_class True."""
    e = entity("Q10", id="SomeClass", claims={"P3": [ref("Q1")]})
    g = graph(*bench_vocab(), e)
    assert shapes.is_class(g, e) is True


def test_is_class_false() -> None:
    """An entity typed something other than Class dispatches is_class False."""
    e = entity("Q10", id="SomeThing", claims={"P3": [ref("Q4")]})
    g = graph(*bench_vocab(), e)
    assert shapes.is_class(g, e) is False


def test_is_class_none_when_blind() -> None:
    """An entity with no local typing gives None, not False."""
    e = entity("Q10", id="Untyped")
    g = graph(*bench_vocab(), e)
    assert shapes.is_class(g, e) is None


def test_is_property() -> None:
    """is_property mirrors is_class against the Property well-known item."""
    e = entity("Q10", id="SomeConstraint", claims={"P3": [ref("Q2")]})
    g = graph(*bench_vocab(), e)
    assert shapes.is_property(g, e) is True
    assert shapes.is_property(g, g.entities["Q10"]) is True
    other = entity("Q20", id="SomeClass", claims={"P3": [ref("Q1")]})
    assert shapes.is_property(graph(*bench_vocab(), other), other) is False


def test_reach_thing() -> None:
    """subClassOf -> Thing reaches THING."""
    e = entity("Q10", id="A", claims={"P4": [ref("Q4")]})
    g = graph(*bench_vocab(), e)
    assert shapes.reach(g, e) is Reach.THING


def test_reach_enumeration() -> None:
    """subClassOf -> Enumeration reaches ENUMERATION."""
    e = entity("Q10", id="A", claims={"P4": [ref("Q3")]})
    g = graph(*bench_vocab(), e)
    assert shapes.reach(g, e) is Reach.ENUMERATION


def test_reach_both() -> None:
    """Two subClassOf branches, one reaching each root, reach BOTH."""
    thing_branch = entity("Q11", id="B", claims={"P4": [ref("Q4")]})
    enum_branch = entity("Q12", id="C", claims={"P4": [ref("Q3")]})
    e = entity("Q10", id="A", claims={"P4": [ref("Q11"), ref("Q12")]})
    g = graph(*bench_vocab(), e, thing_branch, enum_branch)
    assert shapes.reach(g, e) is Reach.BOTH


def test_reach_neither() -> None:
    """A chain that dead-ends at a defined entity with no subClassOf reaches NEITHER."""
    dead_end = entity("Q11", id="D")
    e = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    g = graph(*bench_vocab(), e, dead_end)
    assert shapes.reach(g, e) is Reach.NEITHER


def test_reach_blind() -> None:
    """A chain that dead-ends at a dcid-only reference reaches BLIND."""
    reference = entity("Q11", dcid="schema:Organization")
    e = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    g = graph(*bench_vocab(), e, reference)
    assert shapes.reach(g, e) is Reach.BLIND


def test_reach_two_hop_chain() -> None:
    """A chain reaches Thing across two subClassOf hops."""
    middle = entity("Q11", id="B", claims={"P4": [ref("Q4")]})
    e = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    g = graph(*bench_vocab(), e, middle)
    assert shapes.reach(g, e) is Reach.THING


def test_reach_memoises_a_shared_target() -> None:
    """Two branches sharing a target compute it once and agree."""
    shared = entity("Q11", id="Shared", claims={"P4": [ref("Q3")]})
    e = entity("Q10", id="A", claims={"P4": [ref("Q11"), ref("Q11")]})
    g = graph(*bench_vocab(), e, shared)
    assert shapes.reach(g, e) is Reach.ENUMERATION


def test_reach_through_a_cycle_terminates() -> None:
    """A chain that runs into a subClassOf cycle terminates deterministically."""
    y = entity("Q11", id="Y", claims={"P4": [ref("Q12")]})
    z = entity("Q12", id="Z", claims={"P4": [ref("Q11")]})
    e = entity("Q10", id="X", claims={"P4": [ref("Q11")]})
    g = graph(*bench_vocab(), e, y, z)
    assert shapes.reach(g, e) is Reach.NEITHER


def test_cycles_two_cycle() -> None:
    """A mutual subClassOf pair is reported as one sorted 2-tuple."""
    a = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    b = entity("Q11", id="B", claims={"P4": [ref("Q10")]})
    g = graph(*bench_vocab(), a, b)
    assert shapes.cycles(g, "subClassOf") == [("Q10", "Q11")]


def test_cycles_three_cycle() -> None:
    """A three-node ring is reported as one sorted 3-tuple."""
    a = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    b = entity("Q11", id="B", claims={"P4": [ref("Q12")]})
    c = entity("Q12", id="C", claims={"P4": [ref("Q10")]})
    g = graph(*bench_vocab(), a, b, c)
    assert shapes.cycles(g, "subClassOf") == [("Q10", "Q11", "Q12")]


def test_cycles_self_loop() -> None:
    """An entity stating subClassOf on itself is a size-1 cycle."""
    a = entity("Q10", id="A", claims={"P4": [ref("Q10")]})
    g = graph(*bench_vocab(), a)
    assert shapes.cycles(g, "subClassOf") == [("Q10",)]


def test_cycles_diamond_is_not_a_cycle() -> None:
    """A diamond shape with no back edge reports no cycles."""
    a = entity("Q10", id="A", claims={"P4": [ref("Q11"), ref("Q12")]})
    b = entity("Q11", id="B", claims={"P4": [ref("Q13")]})
    c = entity("Q12", id="C", claims={"P4": [ref("Q13")]})
    d = entity("Q13", id="D")
    g = graph(*bench_vocab(), a, b, c, d)
    assert shapes.cycles(g, "subClassOf") == []


def test_cycles_deterministic_under_permutation() -> None:
    """The same cycle is found regardless of the order entities are given in."""
    a = entity("Q10", id="A", claims={"P4": [ref("Q11")]})
    b = entity("Q11", id="B", claims={"P4": [ref("Q10")]})
    forward = graph(*bench_vocab(), a, b)
    backward = graph(*bench_vocab(), b, a)
    assert (
        shapes.cycles(forward, "subClassOf")
        == shapes.cycles(backward, "subClassOf")
        == [("Q10", "Q11")]
    )


def test_dispatch_s1_reference() -> None:
    """A dcid-carrying entity dispatches REFERENCE."""
    g = graph(*bench_vocab())
    result = shapes.dispatch(g, g.entities["Q4"])
    assert result == Dispatch(Shape.REFERENCE)


def test_dispatch_s2_minted_property() -> None:
    """An id-carrying property with no typeOf dispatches MINTED_PROPERTY."""
    e = entity("P9", kind=Kind.PROPERTY, id="financingPurpose")
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.MINTED_PROPERTY)


def test_dispatch_s3_constraint_property() -> None:
    """An id-carrying item typed Property dispatches CONSTRAINT_PROPERTY."""
    e = entity("Q10", id="SomeConstraint", claims={"P3": [ref("Q2")]})
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.CONSTRAINT_PROPERTY)


def test_dispatch_s4_class_or_list() -> None:
    """An id-carrying item typed Class dispatches CLASS_OR_LIST."""
    e = entity("Q10", id="SomeClass", claims={"P3": [ref("Q1")]})
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.CLASS_OR_LIST)


def test_dispatch_s5_value() -> None:
    """typeOf targeting a value list (reaches Enumeration) dispatches VALUE."""
    value_list = entity(
        "Q11", id="SomeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    e = entity("Q10", id="SomeValue", claims={"P3": [ref("Q11")]})
    g = graph(*bench_vocab(), e, value_list)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.VALUE)


def test_dispatch_s6_individual() -> None:
    """typeOf targeting a class (reaches Thing) dispatches INDIVIDUAL."""
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity("Q10", id="SomeIndividual", claims={"P3": [ref("Q11")]})
    g = graph(*bench_vocab(), e, a_class)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.INDIVIDUAL)


def test_dispatch_s5_or_s6_blind() -> None:
    """A dead-end reachability chain dispatches the value/individual union, skipped."""
    reference = entity("Q12", dcid="schema:Organization")
    ambiguous_class = entity(
        "Q11", id="Ambiguous", claims={"P3": [ref("Q1")], "P4": [ref("Q12")]}
    )
    e = entity("Q10", id="MaybeValueOrIndividual", claims={"P3": [ref("Q11")]})
    g = graph(*bench_vocab(), e, ambiguous_class, reference)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.VALUE_OR_INDIVIDUAL
    assert result.skip is True


def test_dispatch_s7_typeof_absent() -> None:
    """An id-carrying item with no typeOf dispatches UNDETERMINED, not skipped."""
    e = entity("Q10", id="NoType")
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is False


def test_dispatch_s7_typeof_multiple() -> None:
    """An id-carrying item with two typeOf statements dispatches UNDETERMINED, not skipped."""
    e = entity("Q10", id="TwoTypes", claims={"P3": [ref("Q1"), ref("Q4")]})
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is False


def test_dispatch_s7_typeof_unresolvable() -> None:
    """An id-carrying item with a dangling typeOf dispatches UNDETERMINED, skipped.

    G1 already reports the dangling reference, so the shape layer skips
    instead of raising a second finding for the same fault.
    """
    e = entity("Q10", id="Dangling", claims={"P3": [ref("Q999")]})
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is True


def test_dispatch_neither_identifier() -> None:
    """An entity with neither id nor dcid dispatches UNDETERMINED, skipped."""
    e = entity("Q10")
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is True
    assert result.reason == "carries neither id nor dcid"


def test_dispatch_cycle_member_skips() -> None:
    """typeOf targeting a subClassOf cycle member dispatches UNDETERMINED, skipped."""
    a = entity("Q10", id="CycleA", claims={"P3": [ref("Q1")], "P4": [ref("Q11")]})
    b = entity("Q11", id="CycleB", claims={"P3": [ref("Q1")], "P4": [ref("Q10")]})
    e = entity("Q12", id="UsesCycle", claims={"P3": [ref("Q10")]})
    g = graph(*bench_vocab(), a, b, e)
    cyclic = shapes.cycle_members(g, ("subClassOf",))
    assert cyclic == frozenset({"Q10", "Q11"})
    result = shapes.dispatch(g, e, cyclic=cyclic)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is True


def test_dispatch_missing_thing_individual_degrades() -> None:
    """Thing missing only blocks the reachability branch: an individual degrades."""
    vocab_without_thing = [e for e in bench_vocab() if e.qid != "Q4"]
    base = entity("Q10", id="Base", claims={"P3": [ref("Q1")]})
    e = entity("Q11", id="Ind", claims={"P3": [ref("Q10")]})
    g = graph(*vocab_without_thing, base, e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is True


def test_dispatch_missing_thing_class_or_list_unaffected() -> None:
    """Thing missing does not block a class from dispatching CLASS_OR_LIST."""
    vocab_without_thing = [e for e in bench_vocab() if e.qid != "Q4"]
    e = entity("Q10", id="SomeClass", claims={"P3": [ref("Q1")]})
    g = graph(*vocab_without_thing, e)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.CLASS_OR_LIST)


def test_dispatch_missing_thing_constraint_property_unaffected() -> None:
    """Thing missing does not block a constraint property from dispatching."""
    vocab_without_thing = [e for e in bench_vocab() if e.qid != "Q4"]
    e = entity("Q10", id="SomeConstraint", claims={"P3": [ref("Q2")]})
    g = graph(*vocab_without_thing, e)
    result = shapes.dispatch(g, e)
    assert result == Dispatch(Shape.CONSTRAINT_PROPERTY)


def test_dispatch_missing_class_degrades_before_reach() -> None:
    """Class missing blocks the class-or-property check, degrading to UNDETERMINED."""
    vocab_without_class = [e for e in bench_vocab() if e.qid != "Q1"]
    e = entity("Q10", id="Whatever", claims={"P3": [ref("Q3")]})
    g = graph(*vocab_without_class, e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.UNDETERMINED
    assert result.skip is True


def test_dispatch_ignores_dcid_even_with_id() -> None:
    """An entity carrying both id and dcid dispatches REFERENCE (dcid wins first)."""
    e = entity("Q10", id="Both", dcid="schema:Both")
    g = graph(*bench_vocab(), e)
    result = shapes.dispatch(g, e)
    assert result.shape is Shape.REFERENCE


def test_type_target() -> None:
    """type_target resolves a single, resolvable typeOf; else None."""
    e = entity("Q10", id="A", claims={"P3": [ref("Q1")]})
    g = graph(*bench_vocab(), e)
    assert shapes.type_target(g, e) is g.entities["Q1"]
    untyped = entity("Q11", id="B", claims={"P3": [lit("not-a-ref")]})
    assert shapes.type_target(graph(*bench_vocab(), untyped), untyped) is None
