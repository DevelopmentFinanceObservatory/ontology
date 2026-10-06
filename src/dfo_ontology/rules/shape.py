"""S1-S7: the shape allowlist, an ordered dispatch checked against a per-shape allowlist.

`id` and `dcid` statements never reach this layer — `Graph.statements()` already
excludes them, structurally, for every shape. A predicate outside the matched
shape's list is rejected everywhere until a shape opts into it (§9.1 of the brief).
"""

from dfo_ontology import config, shapes
from dfo_ontology.model import Entity, Finding, Graph, Result
from dfo_ontology.shapes import Shape

# Any node the DFO emits may be flagged once as not yet final. A reference emits
# nothing, so it has nothing to flag.
PROVISIONAL: dict[str, tuple[int, int | None]] = {"isProvisional": (0, 1)}

ALLOWED: dict[Shape, dict[str, tuple[int, int | None]]] = {
    # A reference emits no node, so a code on one reaches nobody through the
    # MCF. It reaches them through codes.csv: stating that DAC 625 is
    # country/AFG is how a pipeline resolves a source code to a global node
    # the DFO does not own. Cardinalities match the individual shape, since a
    # reference is an individual that happens to live outside the DFO.
    Shape.REFERENCE: {
        "typeOf": (0, 1),
        "dacCode": (0, None),
        "imfEconomyCode": (0, 1),
        "wbCounterpartCode": (0, 1),
        "wbEconomyCode": (0, 1),
    },
    Shape.MINTED_PROPERTY: {
        "domainIncludes": (1, None),
        "rangeIncludes": (1, None),
        "subPropertyOf": (0, 1),
        **PROVISIONAL,
    },
    Shape.CONSTRAINT_PROPERTY: {
        "typeOf": (1, 1),
        "domainIncludes": (1, None),
        "rangeIncludes": (1, None),
        "subPropertyOf": (0, 1),
        **PROVISIONAL,
    },
    Shape.CLASS_OR_LIST: {"typeOf": (1, 1), "subClassOf": (0, None), **PROVISIONAL},
    # A value's own code identifies it, so classificationCode is capped at one;
    # a wbCode records the same concept's code in a World Bank list, and one
    # concept can sit in more than one of those.
    Shape.VALUE: {
        "typeOf": (1, 1),
        "specializationOf": (0, 1),
        "classificationCode": (0, 1),
        "wbCode": (0, None),
        **PROVISIONAL,
    },
    # A register can reach one thing through more than one code, so dacCode is
    # uncapped where an ISO code, assigned one per currency, is not. The two
    # World Bank lists name each entity once: the economy list holds one code
    # per economy, the counterpart list one per creditor. M49 likewise assigns
    # one code per country, area or region, and the IMF one per economy or group
    # of economies. hasMember is uncapped and sits here alone, not on the value
    # shape: a grouping lists its members, an enumeration value has none.
    # nationalCurrencyOf is uncapped because several places share one national
    # currency. G10 keeps it to a current currency, and G11 to one currency per
    # place.
    Shape.INDIVIDUAL: {
        "typeOf": (1, 1),
        "nationalCurrencyOf": (0, None),
        "dacCode": (0, None),
        "hasMember": (0, None),
        "imfEconomyCode": (0, 1),
        "iso4217AlphaCode": (0, 1),
        "iso4217NumericCode": (0, 1),
        "currencyStatus": (0, 1),
        "m49Code": (0, 1),
        "wbCounterpartCode": (0, 1),
        "wbEconomyCode": (0, 1),
        **PROVISIONAL,
    },
}
ALLOWED[Shape.VALUE_OR_INDIVIDUAL] = {
    **ALLOWED[Shape.VALUE],
    **ALLOWED[Shape.INDIVIDUAL],
}

SHAPE_LABELS: dict[Shape, str] = {
    Shape.REFERENCE: "a reference",
    Shape.MINTED_PROPERTY: "a minted working-set property",
    Shape.CONSTRAINT_PROPERTY: "a constraint property",
    Shape.CLASS_OR_LIST: "a class or value list",
    Shape.VALUE: "a value",
    Shape.INDIVIDUAL: "an individual",
    Shape.VALUE_OR_INDIVIDUAL: "a value or individual",
}


def _allowed_for(graph: Graph, shape: Shape) -> dict[str, tuple[int, int | None]]:
    """This shape's allowlist, dropping code properties not minted on the bench."""
    allowed = dict(ALLOWED[shape])
    for property_id in config.CODE_PROPERTY_IDS:
        if property_id in allowed and graph.entity_by_id(property_id) is None:
            del allowed[property_id]
    return allowed


def _disallowed_message(shape: Shape, predicate: str) -> str:
    """The message for a predicate the matched shape's allowlist does not carry."""
    if shape is Shape.MINTED_PROPERTY and predicate == "typeOf":
        return "a minted working-set property carries no typeOf; schema:Property is injected"
    return f"not allowed on {SHAPE_LABELS[shape]}"


def _cardinality_message(count: int, minimum: int, maximum: int | None) -> str:
    """The message for a predicate stated an out-of-range number of times."""
    if count < minimum:
        return (
            "must be stated exactly once"
            if maximum == 1
            else "must be stated at least once"
        )
    return (
        "must be stated at most once"
        if maximum == 1
        else f"stated {count} times, at most {maximum} allowed"
    )


def _check_statements(
    graph: Graph, result: Result, entity: Entity, shape: Shape
) -> None:
    """Check this entity's statements against its matched shape's allowlist."""
    allowed = _allowed_for(graph, shape)
    counts: dict[str, int] = {}
    disallowed: set[str] = set()
    for statement in graph.statements(entity):
        counts[statement.predicate] = counts.get(statement.predicate, 0) + 1
        if statement.predicate not in allowed:
            disallowed.add(statement.predicate)

    for predicate in sorted(disallowed):
        result.errors.append(
            Finding(
                shape.value,
                entity=entity,
                predicate=predicate,
                message=_disallowed_message(shape, predicate),
            )
        )

    for predicate, (minimum, maximum) in allowed.items():
        count = counts.get(predicate, 0)
        if count < minimum or (maximum is not None and count > maximum):
            result.errors.append(
                Finding(
                    shape.value,
                    entity=entity,
                    predicate=predicate,
                    message=_cardinality_message(count, minimum, maximum),
                )
            )


def shape_layer(
    graph: Graph, result: Result, *, blocked: frozenset[str], cyclic: frozenset[str]
) -> None:
    """S1-S7: dispatch every entity to its shape, then check it against the allowlist.

    Each entity's rule is guarded on its own id, not the layer as a whole — an
    entity dispatches to exactly one shape, so the guard is which shape id that
    is. The bookkeeping properties are excluded, the same exemption I1 makes:
    they carry neither id nor dcid by design, and I3 is what checks them.

    Args:
        graph: the graph to check.
        result: accumulator to append findings into.
        blocked: preflight-blocked rule ids.
        cyclic: qids known to be in a subClassOf or subPropertyOf cycle.
    """
    bookkeeping = {graph.id_property, graph.dcid_property}
    for entity in graph.entities.values():
        if entity.qid in bookkeeping:
            continue

        dispatch = shapes.dispatch(graph, entity, cyclic=cyclic)
        shape = dispatch.shape

        if shape is Shape.UNDETERMINED:
            if "S7" in blocked:
                continue
            findings = result.skips if dispatch.skip else result.errors
            findings.append(Finding("S7", entity=entity, message=dispatch.reason or ""))
            continue

        if shape is Shape.VALUE_OR_INDIVIDUAL:
            if "S5" in blocked or "S6" in blocked:
                continue
            _check_statements(graph, result, entity, shape)
            result.skips.append(
                Finding("S5|S6", entity=entity, message=dispatch.reason or "")
            )
            continue

        if shape.value in blocked:
            continue
        _check_statements(graph, result, entity, shape)
