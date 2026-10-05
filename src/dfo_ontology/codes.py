"""codes.csv text: the code → dcid mapping, one row per coded entity."""

import csv
import io

from dfo_ontology import config, shapes
from dfo_ontology.model import Entity, Graph, Literal

HEADER = ("list", "code", "dcid", "label", "property")


def subjects(graph: Graph) -> list[Entity]:
    """Every entity a code can sit on: minted nodes and references alike.

    A reference emits no MCF node, but the codes on it are the reason it is
    stated at all — they are what lets a pipeline turn a source code into the
    global dcid. Shared with the report's coverage section so the two agree on
    what counts.

    Args:
        graph: the graph to read.
    """
    return [*graph.defined(), *graph.references()]


def node_dcid(graph: Graph, entity: Entity) -> str:
    """The dcid a code row points at.

    A reference already carries the global node's dcid, prefix and all. A minted
    node is named under this graph's own prefix.

    Args:
        graph: the graph to read the prefix from.
        entity: the coded entity.
    """
    if entity.dcid is not None:
        return entity.dcid
    return f"{graph.prefix}:{entity.id}"


def code_literals(graph: Graph, entity: Entity) -> list[tuple[str, Literal]]:
    """Every literal code on this entity, paired with the property stating it.

    The one definition of "coded", shared with the report's coverage section
    so the two can't drift.

    Args:
        graph: the graph to read statements from.
        entity: the entity whose codes are collected.
    """
    return [
        (property_id, value)
        for property_id in config.CODE_PROPERTY_IDS
        for value in graph.values(entity, property_id)
        if isinstance(value, Literal)
    ]


def render(graph: Graph) -> str:
    """Render codes.csv: the header, then one row per coded entity, sorted.

    Rows sort by (list, code, dcid) — the dcid settles the ties the blank
    list column makes ordinary. The header is present even when there are no
    rows. Dcids carry the minted namespace prefix, the same form the MCF
    uses and the form a pipeline writes into observation cells.

    Args:
        graph: the graph to render, already validated.
    """
    rows = []
    for entity in subjects(graph):
        # Codes on values are unique within their list (G9); a code
        # identifying a thing in a register carries no uniqueness rule, so
        # the property column is what tells the two apart.
        for property_id, code in code_literals(graph, entity):
            rows.append(
                (
                    list_dcid(graph, entity),
                    code.text,
                    node_dcid(graph, entity),
                    entity.label or "",
                    property_id,
                )
            )
    rows.sort()
    buffer = io.StringIO()
    # The stdlib default line terminator is \r\n, which the pre-commit
    # mixed-line-ending hook would rewrite in a committed golden.
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buffer.getvalue()


def list_dcid(graph: Graph, entity: Entity) -> str:
    """The dcid of the value list or class this entity's code sits under.

    A code identifies its subject only within the set it was assigned in, and
    one register can span several such sets, so this is what a consumer filters
    by before joining. A class counts as much as a value list.

    Args:
        graph: the graph to resolve against.
        entity: the coded entity whose `typeOf` target is named.
    """
    target = shapes.type_target(graph, entity)
    if target is None:
        return ""
    if target.dcid is not None:
        return target.dcid  # a reference already carries its own prefix
    return f"{graph.prefix}:{target.id}" if target.id else ""
