"""Provisional nodes: DFO nodes flagged isProvisional → True."""

from dfo_ontology import config
from dfo_ontology.codes import code_literals
from dfo_ontology.model import Entity, Finding, Graph, Ref, bare


def is_provisional(graph: Graph, entity: Entity) -> bool:
    """Whether this entity is flagged isProvisional → True.

    Args:
        graph: the graph to read statements from.
        entity: the entity to check.
    """
    return any(
        target.dcid is not None and bare(target.dcid) == config.TRUE_ID
        for _, target in graph.resolved(entity, config.IS_PROVISIONAL_ID)
    )


def flagged(graph: Graph) -> list[Entity]:
    """Every id-carrying entity flagged provisional, sorted by id.

    Args:
        graph: the graph to read.
    """
    return [e for e in graph.defined() if is_provisional(graph, e)]


def without(graph: Graph) -> Graph:
    """The graph minus its provisional nodes, for writing the MCF and codes.csv.

    Args:
        graph: a graph that passed validation with E1, so nothing kept depends
            on what is taken out.
    """
    left_out = {e.qid for e in flagged(graph)}
    return Graph.build(
        (e for e in graph.entities.values() if e.qid not in left_out),
        id_property=graph.id_property,
        dcid_property=graph.dcid_property,
        prefix=graph.prefix,
        findings=graph.findings,
    )


def exclusion_findings(graph: Graph) -> list[Finding]:
    """E1: nothing left in the MCF or codes.csv depends on a provisional node.

    A node depends on another when a statement points at it, or is made through
    it as a property. Either way, leaving the provisional node out would leave
    the kept one pointing at something the MCF no longer defines. A coded
    reference counts as kept: it emits no node, but its codes.csv row names the
    list its typeOf points at.

    Args:
        graph: the graph to check.
    """
    left_out = {e.qid for e in flagged(graph)}
    kept = [e for e in graph.defined() if e.qid not in left_out]
    kept += [e for e in graph.references() if code_literals(graph, e)]
    findings: list[Finding] = []
    for entity in kept:
        through: set[str] = set()
        for statement in graph.statements(entity):
            if statement.property in left_out and statement.predicate not in through:
                through.add(statement.predicate)
                findings.append(
                    Finding(
                        "E1",
                        entity=entity,
                        predicate=statement.predicate,
                        message="stated through a provisional property, which "
                        "--exclude-provisional leaves out",
                    )
                )
            if isinstance(statement.value, Ref) and statement.value.qid in left_out:
                findings.append(
                    Finding(
                        "E1",
                        entity=entity,
                        predicate=statement.predicate,
                        value=graph.entities[statement.value.qid].id,
                        message="points at a provisional node, which "
                        "--exclude-provisional leaves out",
                    )
                )
    return findings
