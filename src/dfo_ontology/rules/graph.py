"""G1-G11 and A2-A4: whole-graph consistency checks.

`G1` is the only rule allowed to look at `Graph.dangling()`. Every other rule
walks `Graph.resolved()`, which yields resolvable targets only, so a dangling
reference cannot cascade into every rule that would otherwise dereference it.
"""

from dfo_ontology import config, shapes
from dfo_ontology.model import (
    Entity,
    Finding,
    Graph,
    Kind,
    Literal,
    Result,
    Value,
    target_text,
)
from dfo_ontology.shapes import Reach, Shape


def _target_text(graph: Graph, target: Entity) -> str:
    """Render a resolved target the way it would appear in emitted MCF."""
    return target_text(graph, target, fallback=target.qid or "")


def _is_property(graph: Graph, entity: Entity) -> bool:
    """Whether this entity counts as a property for G6's purposes.

    A Wikibase property is one regardless of how it is typed (a minted
    working-set property carries no `typeOf` at all); an item counts only
    when its own stated `typeOf` resolves to the Property well-known item.
    """
    if entity.kind is Kind.PROPERTY:
        return True
    return shapes.is_property(graph, entity) is True


def _g1(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G1: every referenced entity exists.

    The one rule allowed to see a dangling reference; every other rule reaches
    targets through `Graph.resolved()`, so this is the only place one is
    reported.
    """
    if "G1" in blocked:
        return
    for entity in graph.entities.values():
        for predicate, ref in graph.dangling(entity):
            result.errors.append(
                Finding(
                    "G1",
                    entity=entity,
                    predicate=predicate,
                    value=ref.qid,
                    message="target does not exist",
                )
            )


def _g2(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G2: typeOf targets Class itself, or an item typed Class."""
    if "G2" in blocked:
        return
    class_wk = shapes.well_known(graph, shapes.CLASS)
    for entity in graph.entities.values():
        for _, target in graph.resolved(entity, "typeOf"):
            if target is class_wk:
                continue
            classy = shapes.is_class(graph, target)
            if classy is None:
                result.skips.append(
                    Finding(
                        "G2",
                        entity=entity,
                        predicate="typeOf",
                        value=_target_text(graph, target),
                        message="target carries no local typing",
                    )
                )
            elif not classy:
                result.errors.append(
                    Finding(
                        "G2",
                        entity=entity,
                        predicate="typeOf",
                        value=_target_text(graph, target),
                        message="not typed Class",
                    )
                )


def _check_domain_range(
    graph: Graph,
    result: Result,
    *,
    predicate: str,
    rule: str,
    allow_datatype: bool = False,
) -> None:
    """G3/G4: a domainIncludes/rangeIncludes target carries the right local typing.

    A domain must be a Class: what a property describes is always an entity. A
    range may also be a DataType, which is how Data Commons types Text, Number
    and Date, so a text-valued property's range is not an error.

    Skipped, not failed, when the target is a `dcid`-only reference carrying
    no local typing — nothing about a global node's typing is visible here.

    Args:
        graph: the graph to check.
        result: accumulator to append findings into.
        predicate: the bare predicate whose targets are checked.
        rule: the rule id the findings carry.
        allow_datatype: whether a DataType-typed target is admitted.
    """
    message = "not typed Class or DataType" if allow_datatype else "not typed Class"
    for entity in graph.entities.values():
        for _, target in graph.resolved(entity, predicate):
            classy = shapes.is_class(graph, target)
            if classy is False and allow_datatype:
                classy = shapes.is_datatype(graph, target)
            if classy is None:
                result.skips.append(
                    Finding(
                        rule,
                        entity=entity,
                        predicate=predicate,
                        value=_target_text(graph, target),
                        message="target carries no local typing",
                    )
                )
            elif not classy:
                result.errors.append(
                    Finding(
                        rule,
                        entity=entity,
                        predicate=predicate,
                        value=_target_text(graph, target),
                        message=message,
                    )
                )


def _g5(
    graph: Graph, result: Result, *, blocked: frozenset[str], cyclic: frozenset[str]
) -> None:
    """G5: every id-carrying class reaches exactly one of Thing or Enumeration.

    Scoped to entities dispatching to the class-or-list shape, so the four
    reference items — which carry a local `typeOf` and no `subClassOf` but no
    `id` — never enter `graph.defined()` and never fire. A class caught in a
    `subClassOf` cycle is skipped: G8 already reports the cycle. A chain that
    stops at any other reference passes, since that node's own parents belong
    to Data Commons.
    """
    if "G5" in blocked:
        return
    for entity in graph.defined():
        if entity.qid in cyclic:
            continue
        if (
            shapes.dispatch(graph, entity, cyclic=cyclic).shape
            is not Shape.CLASS_OR_LIST
        ):
            continue
        outcome = shapes.reach(graph, entity)
        if outcome is Reach.BOTH:
            result.errors.append(
                Finding(
                    "G5",
                    entity=entity,
                    message="subClassOf chain reaches both Thing and Enumeration",
                )
            )
        elif outcome is Reach.NEITHER:
            result.errors.append(
                Finding(
                    "G5",
                    entity=entity,
                    message="subClassOf chain reaches neither Thing nor Enumeration",
                )
            )


def _g6(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G6: subPropertyOf connects two properties."""
    if "G6" in blocked:
        return
    for entity in graph.entities.values():
        for _, target in graph.resolved(entity, "subPropertyOf"):
            if not _is_property(graph, target):
                result.errors.append(
                    Finding(
                        "G6",
                        entity=entity,
                        predicate="subPropertyOf",
                        value=_target_text(graph, target),
                        message="target is not a property",
                    )
                )


def _g7(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G7: specializationOf targets a value in the same list.

    Asserted positively — source and target must share the same resolved
    `typeOf` target — never as "not stated to be in a different list". An
    unresolvable end (either side's `typeOf` is absent, ambiguous, or
    unresolvable) does not pass by default.
    """
    if "G7" in blocked:
        return
    for entity in graph.entities.values():
        for _, target in graph.resolved(entity, "specializationOf"):
            source_list = shapes.type_target(graph, entity)
            target_list = shapes.type_target(graph, target)
            if (
                source_list is None
                or target_list is None
                or source_list is not target_list
            ):
                result.errors.append(
                    Finding(
                        "G7",
                        entity=entity,
                        predicate="specializationOf",
                        value=_target_text(graph, target),
                        message="not a value in the same list",
                    )
                )


def _g8(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G8: no cycles in subClassOf, subPropertyOf, or specializationOf.

    One cross-entity finding per cycle, for each predicate separately. All three
    form hierarchies, so a loop in any of them states that two entities are each
    narrower than the other.
    """
    if "G8" in blocked:
        return
    for predicate in ("subClassOf", "subPropertyOf", "specializationOf"):
        for component in shapes.cycles(graph, predicate):
            result.errors.append(
                Finding(
                    "G8",
                    value=f"{predicate} cycle",
                    message=", ".join(component),
                )
            )


def _g9(
    graph: Graph, result: Result, *, blocked: frozenset[str], cyclic: frozenset[str]
) -> None:
    """G9: classificationCode appears only on values, and is unique within its list.

    No-ops when the property is not minted on the bench.
    """
    if "G9" in blocked:
        return
    if graph.entity_by_id(config.CLASSIFICATION_CODE_ID) is None:
        return

    by_list: dict[str, dict[str, list[str]]] = {}
    for entity in graph.entities.values():
        codes = [
            v
            for v in graph.values(entity, "classificationCode")
            if isinstance(v, Literal)
        ]
        if not codes:
            continue

        dispatch = shapes.dispatch(graph, entity, cyclic=cyclic)
        if dispatch.shape not in (Shape.VALUE, Shape.VALUE_OR_INDIVIDUAL):
            for code in codes:
                result.errors.append(
                    Finding(
                        "G9",
                        entity=entity,
                        predicate="classificationCode",
                        value=f'"{code.text}"',
                        message="only allowed on a value",
                    )
                )
            continue

        list_target = shapes.type_target(graph, entity)
        list_key = list_target.qid if list_target is not None else f"?{entity.qid}"
        for code in codes:
            by_list.setdefault(list_key or "", {}).setdefault(code.text, []).append(
                entity.qid or ""
            )

    for codes in by_list.values():
        for code, qids in codes.items():
            if len(qids) > 1:
                result.errors.append(
                    Finding(
                        "G9",
                        value=f'duplicate classificationCode "{code}"',
                        message=", ".join(qids),
                    )
                )


def _g10(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G10: nationalCurrencyOf sits only on a currency whose currencyStatus is current.

    The status is read through `Graph.resolved()`, so a dangling currencyStatus
    reads as not current; G1 reports the dangling reference itself. No-ops when
    nationalCurrencyOf is not minted on the bench.
    """
    if "G10" in blocked:
        return
    if graph.entity_by_id(config.NATIONAL_CURRENCY_OF_ID) is None:
        return

    for entity in graph.entities.values():
        if not graph.values(entity, config.NATIONAL_CURRENCY_OF_ID):
            continue
        current = any(
            target.id == config.CURRENCY_STATUS_CURRENT_ID
            for _, target in graph.resolved(entity, config.CURRENCY_STATUS_ID)
        )
        if not current:
            result.errors.append(
                Finding(
                    "G10",
                    entity=entity,
                    predicate=config.NATIONAL_CURRENCY_OF_ID,
                    message="only allowed on a currency whose currencyStatus is "
                    f"{config.CURRENCY_STATUS_CURRENT_ID}",
                )
            )


def _g11(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """G11: a place is named through nationalCurrencyOf by at most one currency.

    Targets are read through `Graph.resolved()`, so a dangling target is G1's
    alone. No-ops when nationalCurrencyOf is not minted on the bench.
    """
    if "G11" in blocked:
        return
    if graph.entity_by_id(config.NATIONAL_CURRENCY_OF_ID) is None:
        return

    currencies: dict[str, tuple[Entity, set[str]]] = {}
    for entity in graph.entities.values():
        for _, place in graph.resolved(entity, config.NATIONAL_CURRENCY_OF_ID):
            _, named_by = currencies.setdefault(place.qid or "", (place, set()))
            named_by.add(entity.id or entity.qid or "")

    for place, named_by in currencies.values():
        if len(named_by) > 1:
            result.errors.append(
                Finding(
                    "G11",
                    entity=place,
                    predicate=config.NATIONAL_CURRENCY_OF_ID,
                    message="named by more than one currency — "
                    + ", ".join(sorted(named_by)),
                )
            )


def _a2(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """A2: an orphan — a defined class or value list no other defined entity points at.

    Individuals, values and properties are out of scope: what points at them is
    the pipeline data, which the compiler never reads. Edges from a reference don't
    count, since a reference emits nothing.
    """
    if "A2" in blocked:
        return
    defined = graph.defined()
    referenced: set[str | None] = set()

    for entity in defined:
        predicates = {statement.predicate for statement in graph.statements(entity)}
        for predicate in predicates:
            for _, target in graph.resolved(entity, predicate):
                if target is not entity:
                    referenced.add(target.qid)

    for entity in defined:
        if shapes.is_class(graph, entity) is True and entity.qid not in referenced:
            result.advisories.append(
                Finding(
                    "A2",
                    entity=entity,
                    message="orphan — nothing on the bench points at it",
                )
            )


def _node_class(graph: Graph, entity: Entity) -> Entity | None:
    """The class a node is an instance of: Property for a minted property, else its typeOf."""
    if shapes.is_minted_property(entity):
        return shapes.well_known(graph, shapes.PROPERTY)
    return shapes.type_target(graph, entity)


def _minted_on(graph: Graph, entity: Entity) -> list[Entity]:
    """The minted properties this entity's statements are made through, by id."""
    found = {
        statement.property: prop
        for statement in graph.statements(entity)
        if (prop := graph.entity(statement.property)) is not None
        and shapes.is_minted_property(prop)
    }
    return sorted(found.values(), key=lambda prop: prop.id or "")


def _listed(graph: Graph, targets: list[Entity]) -> str:
    """A domain or range as message text, sorted."""
    return ", ".join(sorted(_target_text(graph, target) for target in targets))


def _a3(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """A3: a statement through a minted property sits on a node its domain covers.

    One finding per node and property, however often it is stated. A node with
    no single class is S7's to report, except a reference, whose typeOf is
    optional, so that is a skip.
    """
    if "A3" in blocked:
        return
    for entity in graph.entities.values():
        for prop in _minted_on(graph, entity):
            domain = [target for _, target in graph.resolved(prop, "domainIncludes")]
            if not domain:
                continue  # S2 reports a property with no domain
            node_class = _node_class(graph, entity)
            if node_class is None:
                if entity.dcid is not None:
                    result.skips.append(
                        Finding(
                            "A3",
                            entity=entity,
                            predicate=prop.id,
                            message="carries no typeOf to check against the domain",
                        )
                    )
                continue
            if shapes.within(graph, node_class, domain):
                continue
            node_text = _target_text(graph, node_class)
            result.advisories.append(
                Finding(
                    "A3",
                    entity=entity,
                    predicate=prop.id,
                    value=node_text,
                    message=f"{prop.id}'s domain does not cover {node_text}: "
                    f"it lists {_listed(graph, domain)}",
                )
            )


def _a4(graph: Graph, result: Result, *, blocked: frozenset[str]) -> None:
    """A4: a value stated through a minted property is one its range covers.

    Text needs a data type in the range; an entity needs its class to be, or
    sit under, a class the range lists. One finding per node, property and
    value text. A dangling value is G1's and a value with no single class is
    S7's, except a reference, whose typeOf is optional, so that is a skip.
    """
    if "A4" in blocked:
        return
    for entity in graph.entities.values():
        reported: set[tuple[str, str]] = set()
        for statement in graph.statements(entity):
            prop = graph.entity(statement.property)
            if prop is None or not shapes.is_minted_property(prop):
                continue
            range_ = [target for _, target in graph.resolved(prop, "rangeIncludes")]
            if not range_:
                continue  # S2 reports a property with no range
            outcome = _a4_finding(graph, entity, prop, statement.value, range_)
            if outcome is None:
                continue
            finding, skipped = outcome
            key = (prop.id or "", finding.value or "")
            if key in reported:
                continue
            reported.add(key)
            (result.skips if skipped else result.advisories).append(finding)


def _a4_finding(
    graph: Graph, entity: Entity, prop: Entity, value: Value, range_: list[Entity]
) -> tuple[Finding, bool] | None:
    """A4's finding for one value and whether it is a skip, or None when nothing to say."""
    if isinstance(value, Literal):
        if any(shapes.is_datatype(graph, target) for target in range_):
            return None
        value_text = "text"
    else:
        target = graph.entity(value.qid)
        if target is None:
            return None  # G1 reports the dangling value
        target_class = _node_class(graph, target)
        if target_class is None:
            if target.dcid is None:
                return None
            skip = Finding(
                "A4",
                entity=entity,
                predicate=prop.id,
                value=_target_text(graph, target),
                message="target carries no typeOf to check against the range",
            )
            return skip, True
        if shapes.within(graph, target_class, range_):
            return None
        value_text = (
            f"{_target_text(graph, target)}, typed {_target_text(graph, target_class)}"
        )
    advisory = Finding(
        "A4",
        entity=entity,
        predicate=prop.id,
        value=value_text,
        message=f"{prop.id}'s range does not cover {value_text}: "
        f"it lists {_listed(graph, range_)}",
    )
    return advisory, False


def graph_layer(
    graph: Graph, result: Result, *, blocked: frozenset[str], cyclic: frozenset[str]
) -> None:
    """G1-G11 and A2-A4: whole-graph consistency checks.

    Each rule is guarded on its own id, not the layer as a whole, matching the
    identity and shape layers.

    Args:
        graph: the graph to check.
        result: accumulator to append findings into.
        blocked: preflight-blocked rule ids.
        cyclic: qids known to be in a subClassOf or subPropertyOf cycle.
    """
    _g1(graph, result, blocked=blocked)
    _g2(graph, result, blocked=blocked)
    if "G3" not in blocked:
        _check_domain_range(graph, result, predicate="domainIncludes", rule="G3")
    if "G4" not in blocked:
        _check_domain_range(
            graph, result, predicate="rangeIncludes", rule="G4", allow_datatype=True
        )
    _g5(graph, result, blocked=blocked, cyclic=cyclic)
    _g6(graph, result, blocked=blocked)
    _g7(graph, result, blocked=blocked)
    _g8(graph, result, blocked=blocked)
    _g9(graph, result, blocked=blocked, cyclic=cyclic)
    _g10(graph, result, blocked=blocked)
    _g11(graph, result, blocked=blocked)
    _a2(graph, result, blocked=blocked)
    _a3(graph, result, blocked=blocked)
    _a4(graph, result, blocked=blocked)
