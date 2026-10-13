"""The rulebook gate: preflight vocabulary checks, then per-entity layers.

Findings accumulate into a mutable `Result`; every layer returns `None`, so no
layer can short-circuit the accumulate-never-fail-fast gate. `validate()` is
that enforcement point — no early return, no raise.
"""

from dfo_ontology import provisional, shapes
from dfo_ontology.model import Finding, Graph, Kind, Preflight, Result
from dfo_ontology.rules.graph import graph_layer
from dfo_ontology.rules.identity import identity_layer
from dfo_ontology.rules.shape import shape_layer
from dfo_ontology.shapes import CLASS, ENUMERATION, PROPERTY, THING

__all__ = ["BLOCKED_BY_GAP", "Preflight", "Result", "preflight", "validate"]

STRUCTURAL_PREDICATES = (
    "typeOf",
    "subClassOf",
    "subPropertyOf",
    "domainIncludes",
    "rangeIncludes",
    "specializationOf",
)

# Preflight -> blocked rule ids: a gap in the left column leaves the rules on the
# right with nothing they could check, so they are reported as not-run rather
# than firing once per entity. P2 fires only on ambiguity (two properties
# claiming one bare name); a predicate simply absent from the bench blocks
# nothing, because no statement can be made through it.
#
# Both Class-item gaps reach G3, G4 and A2 as well as G2: all four resolve
# typing through the one Class claimant, so with none or more than one, a node
# typed through the wrong claimant reads as "not typed Class".
BLOCKED_BY_GAP: dict[str, frozenset[str]] = {
    "id property": frozenset(
        "I1 I2 I3 I4 I5 I7 I8 I9 I10 I11 S2 S3 S4 S5 S6 S7 G5 G9 G10 G11 A1 A2 A3 A4".split()
    ),
    "dcid property": frozenset("I1 I2 I3 I6 S1".split()),
    f"{CLASS} item": frozenset("G2 G3 G4 S1 S4 A2".split()),
    f"{PROPERTY} item": frozenset("S3 G6".split()),
    f"{THING} item": frozenset("G5 S6".split()),
    f"{ENUMERATION} item": frozenset("G5 S5".split()),
    "typeOf predicate": frozenset("G2 G5 S3 S4 S5 S6 S7 A2 A3 A4".split()),
    "subClassOf predicate": frozenset("G5 G8 S5 S6 A3 A4".split()),
    "subPropertyOf predicate": frozenset("G6 G8".split()),
    "domainIncludes predicate": frozenset("G3 A3".split()),
    "rangeIncludes predicate": frozenset("G4 A4".split()),
    "specializationOf predicate": frozenset("G7".split()),
}


def validate(graph: Graph, *, exclude_provisional: bool = False) -> Result:
    """Run preflight, then every layer, accumulating findings without failing fast.

    Args:
        graph: the graph to validate.
        exclude_provisional: whether provisional nodes will be left out of the
            MCF, which adds E1.
    """
    pre = preflight(graph)
    cyclic = shapes.cycle_members(graph, ("subClassOf", "subPropertyOf"))
    result = Result(errors=[*graph.findings, *pre.findings], not_run=pre.blocked)
    identity_layer(graph, result, blocked=pre.blocked, cyclic=cyclic)
    shape_layer(graph, result, blocked=pre.blocked, cyclic=cyclic)
    graph_layer(graph, result, blocked=pre.blocked, cyclic=cyclic)
    if exclude_provisional:
        result.errors.extend(provisional.exclusion_findings(graph))
    return result


def preflight(graph: Graph) -> Preflight:
    """Check discovered vocabulary once, so one gap produces one finding.

    Args:
        graph: the graph to check.
    """
    findings: list[Finding] = []
    blocked: set[str] = set()

    for gap, qid in (
        ("id property", graph.id_property),
        ("dcid property", graph.dcid_property),
    ):
        entity = graph.entity(qid)
        if entity is None:
            findings.append(
                Finding("P1", value=qid, message=f"the {gap} ({qid}) does not exist")
            )
            blocked |= BLOCKED_BY_GAP[gap]
        elif entity.kind is not Kind.PROPERTY:
            findings.append(
                Finding(
                    "P1",
                    entity=entity,
                    value=qid,
                    message=f"the {gap} ({qid}) is not a property",
                )
            )
            blocked |= BLOCKED_BY_GAP[gap]

    for name in STRUCTURAL_PREDICATES:
        claimants = graph.properties_named(name)
        if len(claimants) > 1:
            qids = ", ".join(e.qid or "" for e in claimants)
            findings.append(
                Finding(
                    "P2",
                    value=name,
                    message=f"claimed by more than one property: {qids}",
                )
            )
            blocked |= BLOCKED_BY_GAP[f"{name} predicate"]

    for name in (CLASS, PROPERTY, THING, ENUMERATION):
        claimants = shapes.claimants(graph, name)
        if not claimants:
            findings.append(
                Finding("P3", value=name, message=f"the {name} item is missing")
            )
            blocked |= BLOCKED_BY_GAP[f"{name} item"]
        elif len(claimants) > 1:
            qids = ", ".join(e.qid or "" for e in claimants)
            findings.append(
                Finding(
                    "P3", value=name, message=f"claimed by more than one item: {qids}"
                )
            )
            blocked |= BLOCKED_BY_GAP[f"{name} item"]

    return Preflight(findings=tuple(findings), blocked=frozenset(blocked))
