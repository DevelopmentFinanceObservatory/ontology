"""In-memory graph construction helpers shared by every test module.

Not collected by pytest (filename does not match `test_*`).
"""

from collections.abc import Mapping, Sequence

from dfo_ontology.config import PREFIX
from dfo_ontology.model import Entity, Finding, Graph, Kind, Literal, Ref, Result, Value


def entity(
    qid: str,
    *,
    kind: Kind = Kind.ITEM,
    label: str | None = None,
    description: str | None = None,
    aliases: Sequence[str] = (),
    id: str | None = None,
    dcid: str | None = None,
    claims: Mapping[str, Sequence[Value]] | None = None,
) -> Entity:
    """Build an Entity, mirroring how the reader lifts id/dcid onto claims."""
    all_claims: dict[str, list[Value]] = {
        property_qid: list(values) for property_qid, values in (claims or {}).items()
    }
    if id is not None:
        all_claims["P1"] = [Literal(id), *all_claims.get("P1", [])]
    if dcid is not None:
        all_claims["P2"] = [Literal(dcid), *all_claims.get("P2", [])]
    return Entity(
        qid=qid,
        kind=kind,
        label=label,
        description=description,
        aliases=tuple(aliases),
        id=id,
        dcid=dcid,
        claims=all_claims,
    )


def ref(qid: str) -> Ref:
    """Shorthand for Ref(qid)."""
    return Ref(qid)


def lit(text: str) -> Literal:
    """Shorthand for Literal(text)."""
    return Literal(text)


def graph(
    *entities: Entity,
    id_property: str = "P1",
    dcid_property: str = "P2",
    prefix: str = PREFIX,
    findings: Sequence[Finding] = (),
) -> Graph:
    """Build a Graph from entities, delegating to Graph.build."""
    return Graph.build(
        entities,
        id_property=id_property,
        dcid_property=dcid_property,
        prefix=prefix,
        findings=findings,
    )


def errors(result: Result, rule: str) -> list[Finding]:
    """This result's errors matching a rule id."""
    return [f for f in result.errors if f.rule == rule]


def skips(result: Result, rule: str) -> list[Finding]:
    """This result's skips matching a rule id."""
    return [f for f in result.skips if f.rule == rule]


def advisories(result: Result, rule: str) -> list[Finding]:
    """This result's advisories matching a rule id."""
    return [f for f in result.advisories if f.rule == rule]


def bench_vocab() -> list[Entity]:
    """The live bench's vocabulary, as entities.

    P1 id, P2 dcid (both carrying no identifier); P3-P8 the six structural properties
    carrying `dcid:typeOf` ... `dcid:specializationOf`; Q1-Q4
    `schema:Class`/`Property`/`Enumeration`/`Thing`, each with a local `typeOf -> Q1`.
    """
    return [
        entity("P1", kind=Kind.PROPERTY),
        entity("P2", kind=Kind.PROPERTY),
        entity("P3", kind=Kind.PROPERTY, dcid="dcid:typeOf"),
        entity("P4", kind=Kind.PROPERTY, dcid="dcid:subClassOf"),
        entity("P5", kind=Kind.PROPERTY, dcid="dcid:subPropertyOf"),
        entity("P6", kind=Kind.PROPERTY, dcid="dcid:domainIncludes"),
        entity("P7", kind=Kind.PROPERTY, dcid="dcid:rangeIncludes"),
        entity("P8", kind=Kind.PROPERTY, dcid="dcid:specializationOf"),
        entity("Q1", dcid="schema:Class", claims={"P3": [ref("Q1")]}),
        entity("Q2", dcid="schema:Property", claims={"P3": [ref("Q1")]}),
        entity("Q3", dcid="schema:Enumeration", claims={"P3": [ref("Q1")]}),
        entity("Q4", dcid="schema:Thing", claims={"P3": [ref("Q1")]}),
    ]
