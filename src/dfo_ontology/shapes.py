"""Shape dispatch: what kind of MCF node an entity's stated `typeOf` makes it.

Nothing here is derived from inbound edges — `reach` walks only an entity's own
stated `subClassOf` chain, and `dispatch` reads only its own stated `typeOf`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from dfo_ontology.model import Entity, Graph, Kind, Ref, bare

CLASS = "Class"
PROPERTY = "Property"
THING = "Thing"
ENUMERATION = "Enumeration"
DATATYPE = "DataType"


class Shape(StrEnum):
    """The MCF node shape an entity dispatches to."""

    REFERENCE = "S1"
    MINTED_PROPERTY = "S2"
    CONSTRAINT_PROPERTY = "S3"
    CLASS_OR_LIST = "S4"
    VALUE = "S5"
    INDIVIDUAL = "S6"
    VALUE_OR_INDIVIDUAL = "S5|S6"
    UNDETERMINED = "S7"


class Reach(StrEnum):
    """What a stated `subClassOf` chain reaches."""

    THING = "Thing"
    ENUMERATION = "Enumeration"
    BOTH = "both"
    NEITHER = "neither"
    BLIND = "blind"


@dataclass(frozen=True)
class Dispatch:
    """The shape an entity dispatched to, and why."""

    shape: Shape
    reason: str | None = None  # why UNDETERMINED or unresolved; the finding's message
    skip: bool = (
        False  # cause already reported elsewhere -> record a skip, not an error
    )


def claimants(graph: Graph, name: str) -> list[Entity]:
    """Items whose bare dcid equals this name, in qid order.

    Args:
        graph: the graph to search.
        name: the bare well-known name, e.g. "Class".
    """
    return [
        e
        for e in graph.entities.values()
        if e.kind is Kind.ITEM and e.dcid is not None and bare(e.dcid) == name
    ]


def well_known(graph: Graph, name: str) -> Entity | None:
    """The first item claiming this well-known bare dcid name.

    Args:
        graph: the graph to search.
        name: the bare well-known name, e.g. "Thing".
    """
    found = claimants(graph, name)
    return found[0] if found else None


def type_target(graph: Graph, entity: Entity) -> Entity | None:
    """The entity's single resolved `typeOf` target.

    Args:
        graph: the graph to resolve against.
        entity: the entity whose `typeOf` is inspected.

    Returns:
        None when `typeOf` is absent, stated more than once, or does not
        resolve to a known entity.
    """
    values = graph.values(entity, "typeOf")
    if len(values) != 1:
        return None
    value = values[0]
    if not isinstance(value, Ref):
        return None
    return graph.entity(value.qid)


def _resolves_to(graph: Graph, entity: Entity, name: str) -> bool | None:
    """Whether the entity's stated `typeOf` resolves to this well-known item.

    Returns None when the entity carries no local typing (blind).
    """
    target = type_target(graph, entity)
    if target is None:
        return None
    return target is well_known(graph, name)


def is_class(graph: Graph, entity: Entity) -> bool | None:
    """Whether the entity's stated `typeOf` resolves to the Class well-known item.

    Args:
        graph: the graph to resolve against.
        entity: the entity to check.

    Returns:
        None when the entity carries no local typing (blind).
    """
    return _resolves_to(graph, entity, CLASS)


def is_property(graph: Graph, entity: Entity) -> bool | None:
    """Whether the entity's stated `typeOf` resolves to the Property well-known item.

    Args:
        graph: the graph to resolve against.
        entity: the entity to check.

    Returns:
        None when the entity carries no local typing (blind).
    """
    return _resolves_to(graph, entity, PROPERTY)


def is_minted_property(entity: Entity) -> bool:
    """Whether the entity is a working-set property the DFO mints.

    Args:
        entity: the entity to check.
    """
    return (
        entity.kind is Kind.PROPERTY and entity.id is not None and entity.dcid is None
    )


def is_datatype(graph: Graph, entity: Entity) -> bool | None:
    """Whether the entity's stated `typeOf` resolves to the DataType well-known item.

    Data Commons types Text, Number, Date and Boolean as DataType rather than
    Class, so a property's range can land on one.

    Args:
        graph: the graph to resolve against.
        entity: the entity to check.

    Returns:
        None when the entity carries no local typing (blind).
    """
    return _resolves_to(graph, entity, DATATYPE)


def reach(graph: Graph, entity: Entity) -> Reach:
    """Walk the entity's stated `subClassOf` chain to Thing or Enumeration.

    Memoised, with a visiting set so a cycle terminates instead of recursing
    forever. Never reads inbound edges — nothing is derived from what points
    at a node.

    Args:
        graph: the graph to walk.
        entity: the entity whose chain is walked.
    """
    return _reach(graph, entity, {}, set())


def _reach(
    graph: Graph, entity: Entity, memo: dict[str, Reach], visiting: set[str]
) -> Reach:
    qid = entity.qid
    if qid is not None and qid in memo:
        return memo[qid]
    if qid is not None and qid in visiting:
        return Reach.NEITHER  # cycle: this branch contributes nothing

    if entity is well_known(graph, THING):
        return Reach.THING
    if entity is well_known(graph, ENUMERATION):
        return Reach.ENUMERATION

    targets = [target for _, target in graph.resolved(entity, "subClassOf")]
    if not targets:
        result = Reach.BLIND if entity.dcid is not None else Reach.NEITHER
        if qid is not None:
            memo[qid] = result
        return result

    if qid is not None:
        visiting.add(qid)
    reaches_thing = reaches_enum = reaches_blind = False
    for target in targets:
        outcome = _reach(graph, target, memo, visiting)
        if outcome is Reach.THING:
            reaches_thing = True
        elif outcome is Reach.ENUMERATION:
            reaches_enum = True
        elif outcome is Reach.BOTH:
            reaches_thing = reaches_enum = True
        elif outcome is Reach.BLIND:
            reaches_blind = True
    if qid is not None:
        visiting.discard(qid)

    if reaches_thing and reaches_enum:
        result = Reach.BOTH
    elif reaches_thing:
        result = Reach.THING
    elif reaches_enum:
        result = Reach.ENUMERATION
    elif reaches_blind:
        result = Reach.BLIND
    else:
        result = Reach.NEITHER
    if qid is not None:
        memo[qid] = result
    return result


def within(graph: Graph, entity: Entity, classes: Iterable[Entity]) -> bool:
    """Whether the entity is one of these classes, or sits under one.

    Walks only the entity's own stated `subClassOf` chain, so a class Data
    Commons places above a reference is out of sight.

    Args:
        graph: the graph to walk.
        entity: the class to place.
        classes: the classes it may be, or sit under.
    """
    targets = {c.qid for c in classes}
    seen: set[str | None] = set()
    pending = [entity]
    while pending:
        current = pending.pop()
        if current.qid in seen:
            continue
        seen.add(current.qid)
        if current.qid in targets:
            return True
        pending.extend(target for _, target in graph.resolved(current, "subClassOf"))
    return False


def cycles(graph: Graph, predicate: str) -> list[tuple[str, ...]]:
    """Strongly connected components of size > 1, plus self-loops, over stated edges.

    Tarjan's algorithm over `graph.entities` (already qid-sorted). Each member
    tuple and the returned list are sorted, so the result is the same under any
    permutation of the input.

    Args:
        graph: the graph to search.
        predicate: the bare predicate name whose stated edges are walked.
    """
    edges: dict[str, list[str]] = {
        qid: [
            target.qid
            for _, target in graph.resolved(entity, predicate)
            if target.qid is not None
        ]
        for qid, entity in graph.entities.items()
    }

    counter = 0
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    result: list[tuple[str, ...]] = []

    def strongconnect(v: str) -> None:
        nonlocal counter
        index[v] = lowlink[v] = counter
        counter += 1
        stack.append(v)
        on_stack[v] = True
        for w in edges[v]:
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            if len(component) > 1 or v in edges[v]:
                result.append(tuple(sorted(component)))

    for qid in graph.entities:
        if qid not in index:
            strongconnect(qid)

    return sorted(result)


def cycle_members(
    graph: Graph, predicates: Sequence[str] = ("subClassOf",)
) -> frozenset[str]:
    """Qids belonging to any cycle over any of these predicates.

    Args:
        graph: the graph to search.
        predicates: bare predicate names to check.
    """
    members: set[str] = set()
    for predicate in predicates:
        for component in cycles(graph, predicate):
            members.update(component)
    return frozenset(members)


def dispatch(
    graph: Graph, entity: Entity, *, cyclic: frozenset[str] = frozenset()
) -> Dispatch:
    """Dispatch an entity to its MCF shape, in the rulebook's order, first match wins.

    Args:
        graph: the graph to resolve against.
        entity: the entity to dispatch.
        cyclic: qids known to be in a `subClassOf` cycle.
    """
    if entity.dcid is not None:
        return Dispatch(Shape.REFERENCE)
    if entity.id is not None and entity.kind is Kind.PROPERTY:
        return Dispatch(Shape.MINTED_PROPERTY)
    if entity.id is None:
        return Dispatch(
            Shape.UNDETERMINED, reason="carries neither id nor dcid", skip=True
        )

    values = graph.values(entity, "typeOf")
    if not values:
        return Dispatch(Shape.UNDETERMINED, reason="typeOf is absent")
    if len(values) > 1:
        return Dispatch(Shape.UNDETERMINED, reason="typeOf is stated more than once")
    value = values[0]
    if not isinstance(value, Ref):
        return Dispatch(
            Shape.UNDETERMINED, reason="typeOf does not reference an entity"
        )
    target = graph.entity(value.qid)
    if target is None:
        return Dispatch(
            Shape.UNDETERMINED, reason="typeOf target does not exist", skip=True
        )

    if target.qid in cyclic:
        # `cyclic` covers both hierarchy predicates; G8 names which one it was.
        return Dispatch(
            Shape.UNDETERMINED,
            reason="typeOf target is in a subClassOf or subPropertyOf cycle",
            skip=True,
        )

    property_wk = well_known(graph, PROPERTY)
    if property_wk is not None and target is property_wk:
        return Dispatch(Shape.CONSTRAINT_PROPERTY)
    class_wk = well_known(graph, CLASS)
    if class_wk is not None and target is class_wk:
        return Dispatch(Shape.CLASS_OR_LIST)
    if property_wk is None or class_wk is None:
        return Dispatch(
            Shape.UNDETERMINED,
            reason="the Property or Class well-known item is missing from the bench",
            skip=True,
        )

    thing_wk = well_known(graph, THING)
    enum_wk = well_known(graph, ENUMERATION)
    if thing_wk is None or enum_wk is None:
        return Dispatch(
            Shape.UNDETERMINED,
            reason="the Thing or Enumeration well-known item is missing from the bench",
            skip=True,
        )

    outcome = reach(graph, target)
    if outcome is Reach.ENUMERATION:
        return Dispatch(Shape.VALUE)
    if outcome is Reach.THING:
        return Dispatch(Shape.INDIVIDUAL)
    if outcome is Reach.BLIND:
        return Dispatch(Shape.VALUE_OR_INDIVIDUAL)
    if outcome is Reach.BOTH:
        reason = "typeOf target's subClassOf chain reaches both Thing and Enumeration"
    else:
        reason = (
            "typeOf target's subClassOf chain reaches neither Thing nor Enumeration"
        )
    return Dispatch(Shape.UNDETERMINED, reason=reason)
