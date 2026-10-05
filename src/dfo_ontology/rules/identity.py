"""I1-I11 and A1: bookkeeping identity and label/description checks."""

import re
from collections.abc import Iterator

from dfo_ontology import shapes
from dfo_ontology.model import Entity, Finding, Graph, Literal, Result, escape
from dfo_ontology.shapes import Reach, Shape

# An id is a local name, optionally under a namespace segment: `Afghanistan`, or
# `country/PacificIslandsUS` for a node minted into one of Data Commons' own
# namespaces so it sits beside the global nodes it belongs with.
ID_PATTERN = re.compile(r"(?:[a-z][A-Za-z0-9]*/)?[A-Za-z][A-Za-z0-9]*")
MAX_ID_LENGTH = 256
MAX_VALUE_LENGTH = 65_535


def local_name(id_: str) -> str:
    """The part of an id after its namespace segment.

    The namespace is Data Commons' and follows its casing, so only the local
    name is the author's to get right — that is what I9 judges.

    Args:
        id_: the full id.
    """
    return id_.rsplit("/", 1)[-1]


def _emitted_values(graph: Graph, entity: Entity) -> Iterator[tuple[str, str | None]]:
    """(predicate, text) for every value I8 and I11 must check.

    Both rules walk the same value set — label, description, each alias, and
    each literal statement value — so they share this one traversal.
    """
    yield "name", entity.label
    yield "description", entity.description
    for alias in entity.aliases:
        yield "alternateName", alias
    for statement in graph.statements(entity):
        if isinstance(statement.value, Literal):
            yield statement.predicate, statement.value.text


def _check_length(result: Result, entity: Entity, predicate: str, text: str) -> None:
    """I8: no emitted value may exceed 65,535 characters after quote-escaping."""
    length = len(escape(text))
    if length > MAX_VALUE_LENGTH:
        result.errors.append(
            Finding(
                "I8",
                entity=entity,
                predicate=predicate,
                message=(
                    f"is {length} characters after escaping, "
                    f"over the {MAX_VALUE_LENGTH} limit"
                ),
            )
        )


def _check_backslash(result: Result, entity: Entity, predicate: str, text: str) -> None:
    """I11: no emitted value may contain a backslash.

    MCF's format documents `\\"` as the escape for a quote but says nothing
    about a backslash itself, so one cannot be represented safely — gate
    rather than guess at unverified unescaping behaviour.
    """
    if "\\" in text:
        result.errors.append(
            Finding(
                "I11",
                entity=entity,
                predicate=predicate,
                message=(
                    "contains a backslash, which cannot be represented "
                    "safely in MCF and must be removed"
                ),
            )
        )


def _check_casing(
    graph: Graph, result: Result, entity: Entity, *, cyclic: frozenset[str]
) -> None:
    """I9: a property id starts lowercase, every other id starts uppercase.

    Both property shapes count: a minted working-set property and a constraint
    property are the same thing to Data Commons, which names every property in
    camelCase however it was authored here.

    A value list's id ends in Enum, unless its own `subClassOf` chain is blind
    to that question. Skipped entirely for an entity whose shape could not be
    determined — the shape layer already reports that once.
    """
    dispatch = shapes.dispatch(graph, entity, cyclic=cyclic)
    if dispatch.shape is Shape.UNDETERMINED:
        return

    # Judged on the local name: a namespace segment is Data Commons' and carries
    # its casing, not the author's.
    id_ = local_name(entity.id or "")
    if dispatch.shape in (Shape.MINTED_PROPERTY, Shape.CONSTRAINT_PROPERTY):
        if id_[:1].isupper():
            result.errors.append(
                Finding(
                    "I9",
                    entity=entity,
                    value=f'id "{id_}"',
                    message="a property id must start with a lowercase letter",
                )
            )
        return

    if id_[:1].islower():
        result.errors.append(
            Finding(
                "I9",
                entity=entity,
                value=f'id "{id_}"',
                message="must start with an uppercase letter",
            )
        )

    if dispatch.shape is Shape.CLASS_OR_LIST:
        reach = shapes.reach(graph, entity)
        if reach is Reach.ENUMERATION and not id_.endswith("Enum"):
            result.errors.append(
                Finding(
                    "I9",
                    entity=entity,
                    value=f'id "{id_}"',
                    message="a value list's id must end in Enum",
                )
            )


def identity_layer(
    graph: Graph, result: Result, *, blocked: frozenset[str], cyclic: frozenset[str]
) -> None:
    """I1-I11 and A1: bookkeeping identity and label/description checks.

    Each rule is guarded on its own id rather than the layer as a whole:
    I1 sits in both bookkeeping gaps (id and dcid), so a layer-wide guard on
    it would skip every other rule whenever either gap fired, even the ones
    the other gap leaves perfectly able to run.

    Args:
        graph: the graph to check.
        result: accumulator to append findings into.
        blocked: preflight-blocked rule ids.
        cyclic: qids known to be in a subClassOf or subPropertyOf cycle.
    """
    bookkeeping = {graph.id_property, graph.dcid_property}

    # I1: exactly one of id/dcid. The two bookkeeping properties are exempt —
    # I3 checks them, and they are expected to carry neither.
    if "I1" not in blocked:
        for entity in graph.entities.values():
            if entity.qid in bookkeeping:
                continue
            has_id = entity.id is not None
            has_dcid = entity.dcid is not None
            if not has_id and not has_dcid:
                result.errors.append(
                    Finding("I1", entity=entity, message="carries neither id nor dcid")
                )
            elif has_id and has_dcid:
                result.errors.append(
                    Finding("I1", entity=entity, message="carries both id and dcid")
                )

    # I2: at most one statement of each, counted from claims, not the lifted field.
    if "I2" not in blocked:
        for entity in graph.entities.values():
            id_count = len(entity.claims.get(graph.id_property, []))
            if id_count > 1:
                result.errors.append(
                    Finding(
                        "I2",
                        entity=entity,
                        predicate="id",
                        message=f"stated {id_count} times, at most one allowed",
                    )
                )
            dcid_count = len(entity.claims.get(graph.dcid_property, []))
            if dcid_count > 1:
                result.errors.append(
                    Finding(
                        "I2",
                        entity=entity,
                        predicate="dcid",
                        message=f"stated {dcid_count} times, at most one allowed",
                    )
                )

    # I3: the two bookkeeping properties carry neither identifier themselves.
    if "I3" not in blocked:
        for qid, label in (
            (graph.id_property, "id property"),
            (graph.dcid_property, "dcid property"),
        ):
            entity = graph.entity(qid)
            if entity is not None and (
                entity.id is not None or entity.dcid is not None
            ):
                result.errors.append(
                    Finding(
                        "I3",
                        entity=entity,
                        message=f"the {label} carries an identifier of its own",
                    )
                )

    # I4: id syntax.
    if "I4" not in blocked:
        for entity in graph.defined():
            if not ID_PATTERN.fullmatch(entity.id or ""):
                result.errors.append(
                    Finding(
                        "I4",
                        entity=entity,
                        value=f'id "{entity.id}"',
                        message=(
                            "must start with a letter and contain only letters and "
                            "digits, optionally under a lowercase namespace segment "
                            "such as country/"
                        ),
                    )
                )

    # I5: id uniqueness, cross-entity.
    if "I5" not in blocked:
        for id_, qids in graph.by_id.items():
            if len(qids) > 1:
                result.errors.append(
                    Finding(
                        "I5",
                        value=f'duplicate id "{id_}"',
                        message=", ".join(qids),
                    )
                )

    # I6: dcid carries a prefix, and is unique.
    if "I6" not in blocked:
        for entity in graph.references():
            dcid = entity.dcid or ""
            if ":" not in dcid:
                result.errors.append(
                    Finding(
                        "I6",
                        entity=entity,
                        value=f'dcid "{dcid}"',
                        message="must carry a prefix",
                    )
                )
        for dcid, qids in graph.by_dcid.items():
            if len(qids) > 1:
                result.errors.append(
                    Finding(
                        "I6",
                        value=f'duplicate dcid "{dcid}"',
                        message=", ".join(qids),
                    )
                )

    # I7: the prefixed id's length.
    if "I7" not in blocked:
        for entity in graph.defined():
            full = f"{graph.prefix}:{entity.id}"
            if len(full) > MAX_ID_LENGTH:
                result.errors.append(
                    Finding(
                        "I7",
                        entity=entity,
                        message=(
                            f'"{full}" is {len(full)} characters, '
                            f"over the {MAX_ID_LENGTH} limit"
                        ),
                    )
                )

    # I8: every emitted value, measured after quote-escaping.
    # I11: no emitted value may contain a backslash. Both walk the same
    # value set, via _emitted_values, so one traversal serves them.
    if "I8" not in blocked or "I11" not in blocked:
        for entity in graph.defined():
            for predicate, text in _emitted_values(graph, entity):
                if text is None:
                    continue
                if "I8" not in blocked:
                    _check_length(result, entity, predicate, text)
                if "I11" not in blocked:
                    _check_backslash(result, entity, predicate, text)

    # I9: shape-aware casing.
    if "I9" not in blocked:
        for entity in graph.defined():
            _check_casing(graph, result, entity, cyclic=cyclic)

    # I10: every id-carrying entity has an English label.
    if "I10" not in blocked:
        for entity in graph.defined():
            if entity.label is None:
                result.errors.append(
                    Finding("I10", entity=entity, message="has no English label")
                )

    # A1: a missing description is advisory, not a gate failure.
    if "A1" not in blocked:
        for entity in graph.defined():
            if entity.description is None:
                result.advisories.append(
                    Finding("A1", entity=entity, message="no English description")
                )
