"""S1-S7: an ordered dispatch, each shape checked against what it may carry.

`id` and `dcid` statements never reach this layer — `Graph.statements()` already
excludes them, structurally, for every shape. Each shape lists the structural
statements it may carry. A property the DFO mints may sit on any node the DFO
emits, and where it belongs is A3's and A4's question; a reference emits no
node, so it carries only codes.
"""

from dfo_ontology import config, shapes
from dfo_ontology.model import Entity, Finding, Graph, Result
from dfo_ontology.shapes import Shape

type Counts = dict[str, tuple[int, int | None]]

# Any node the DFO emits may be flagged once as not yet final. A reference emits
# nothing, so it has nothing to flag.
PROVISIONAL: Counts = {"isProvisional": (0, 1)}

ALLOWED: dict[Shape, Counts] = {
    Shape.REFERENCE: {"typeOf": (0, 1)},
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
    Shape.VALUE: {"typeOf": (1, 1), "specializationOf": (0, 1), **PROVISIONAL},
    Shape.INDIVIDUAL: {"typeOf": (1, 1), **PROVISIONAL},
}
ALLOWED[Shape.VALUE_OR_INDIVIDUAL] = {
    **ALLOWED[Shape.VALUE],
    **ALLOWED[Shape.INDIVIDUAL],
}

# Minted properties a node states at most once. Each register here assigns one
# code per thing: ISO one per currency, M49 one per country, area or region, the
# IMF one per economy or group of economies, and the World Bank's economy and
# counterpart lists one per economy and per creditor. A value's own code
# identifies it, and a currency has one status. Any other minted property may
# repeat: DAC reaches one thing through several codes, a concept can sit in more
# than one World Bank list, a grouping lists every member, and several places
# share one national currency.
SINGLE_VALUED = frozenset(
    {
        "classificationCode",
        "currencyStatus",
        "imfEconomyCode",
        "iso4217AlphaCode",
        "iso4217NumericCode",
        "m49Code",
        "wbCounterpartCode",
        "wbEconomyCode",
    }
)

SHAPE_LABELS: dict[Shape, str] = {
    Shape.REFERENCE: "a reference",
    Shape.MINTED_PROPERTY: "a minted working-set property",
    Shape.CONSTRAINT_PROPERTY: "a constraint property",
    Shape.CLASS_OR_LIST: "a class or value list",
    Shape.VALUE: "a value",
    Shape.INDIVIDUAL: "an individual",
    Shape.VALUE_OR_INDIVIDUAL: "a value or individual",
}


def _minted_counts(graph: Graph) -> Counts:
    """Every property the DFO mints on this bench, with how often a node may state it.

    Args:
        graph: the graph to search.
    """
    return {
        name: (0, 1) if name in SINGLE_VALUED else (0, None)
        for entity in graph.entities.values()
        if shapes.is_minted_property(entity) and (name := entity.id) is not None
    }


def _allowed_for(shape: Shape, minted: Counts) -> Counts:
    """What this shape may carry: its structural statements, then minted properties.

    A reference emits no node, so a statement on it reaches a consumer only
    through codes.csv, which reads only the code properties.
    """
    if shape is Shape.REFERENCE:
        minted = {p: c for p, c in minted.items() if p in config.CODE_PROPERTY_IDS}
    return {**minted, **ALLOWED[shape]}


def _disallowed_message(shape: Shape, predicate: str, minted: Counts) -> str:
    """The message for a predicate the matched shape does not carry."""
    if shape is Shape.MINTED_PROPERTY and predicate == "typeOf":
        return "a minted working-set property carries no typeOf; schema:Property is injected"
    if shape is Shape.REFERENCE and predicate in minted:
        return "a reference emits no node, so it may carry only the code properties codes.csv reads"
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
    graph: Graph, result: Result, entity: Entity, shape: Shape, minted: Counts
) -> None:
    """Check this entity's statements against what its matched shape may carry."""
    allowed = _allowed_for(shape, minted)
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
                message=_disallowed_message(shape, predicate, minted),
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
    """S1-S7: dispatch every entity to its shape, then check what it carries.

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
    minted = _minted_counts(graph)
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
            _check_statements(graph, result, entity, shape, minted)
            continue

        if shape.value in blocked:
            continue
        _check_statements(graph, result, entity, shape, minted)
