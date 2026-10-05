"""In-memory graph model: entities, statements, values, and findings."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


class Kind(StrEnum):
    """Wikibase entity kind."""

    ITEM = "item"
    PROPERTY = "property"


@dataclass(frozen=True)
class Ref:
    """A reference to another entity, by qid."""

    qid: str


@dataclass(frozen=True)
class Literal:
    """A string value."""

    text: str


type Value = Ref | Literal


@dataclass(frozen=True)
class Statement:
    """One claim: the property it was made through, its predicate, and its value."""

    property: str  # property qid the statement was made through
    predicate: str  # bare predicate name, or the property qid when undiscoverable
    value: Value


@dataclass(frozen=True)
class Finding:
    """A reader or validation finding, tagged with the rule id it belongs to."""

    rule: str
    entity: Entity | None = None
    predicate: str | None = None
    value: str | None = None  # display-ready text; rules quote string values themselves
    message: str = ""


@dataclass(frozen=True)
class Preflight:
    """Vocabulary findings and the rule ids they leave unable to run."""

    findings: tuple[Finding, ...]
    blocked: frozenset[str]


@dataclass
class Result:
    """Findings accumulated across every layer, by severity."""

    errors: list[Finding] = field(default_factory=list)
    advisories: list[Finding] = field(default_factory=list)
    skips: list[Finding] = field(default_factory=list)
    not_run: frozenset[str] = frozenset()

    @property
    def ok(self) -> bool:
        """True when nothing blocks emission."""
        return not self.errors


@dataclass
class Entity:
    """One Wikibase entity: its bookkeeping identifiers and its claims."""

    qid: str | None
    kind: Kind
    label: str | None = None
    description: str | None = None
    aliases: tuple[str, ...] = ()
    id: str | None = None
    dcid: str | None = None
    claims: dict[str, list[Value]] = field(
        default_factory=dict
    )  # property qid -> values


def bare(value: str) -> str:
    """Strip everything up to the last colon.

    Args:
        value: a dcid, e.g. "schema:Class"; unchanged if it carries no colon.
    """
    return value.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class Graph:
    """The bench's entities plus every index derived from them, deterministically."""

    entities: dict[str, Entity]  # qid -> entity, inserted in sorted-qid order
    by_id: dict[str, list[str]]  # id -> claimant qids, sorted
    by_dcid: dict[str, list[str]]  # dcid -> claimant qids, sorted
    predicate_names: dict[str, str]  # property qid -> bare predicate name
    properties_by_name: dict[
        str, str
    ]  # bare predicate name -> first claimant property qid
    property_claimants: dict[str, list[str]]  # bare predicate name -> claimant qids
    id_property: str
    dcid_property: str
    prefix: str
    findings: tuple[Finding, ...] = ()  # reader findings R1-R3

    @classmethod
    def build(
        cls,
        entities: Iterable[Entity],
        *,
        id_property: str,
        dcid_property: str,
        prefix: str,
        findings: Sequence[Finding] = (),
    ) -> Graph:
        """Sort entities by qid and build every index from that single order.

        Args:
            entities: entities to index, in any order.
            id_property: the property qid carrying the dfo id.
            dcid_property: the property qid carrying the dcid.
            prefix: the namespace prefix minted nodes are written under.
            findings: reader findings (R1-R3) carried onto the graph.
        """
        ordered = sorted(entities, key=lambda e: e.qid or "")
        indexed: dict[str, Entity] = {}
        by_id: dict[str, list[str]] = {}
        by_dcid: dict[str, list[str]] = {}
        predicate_names: dict[str, str] = {}
        property_claimants: dict[str, list[str]] = {}

        for entity in ordered:
            if entity.qid is None:
                continue
            indexed[entity.qid] = entity
            if entity.id is not None:
                by_id.setdefault(entity.id, []).append(entity.qid)
            if entity.dcid is not None:
                by_dcid.setdefault(entity.dcid, []).append(entity.qid)
            if entity.kind is not Kind.PROPERTY:
                continue
            if entity.dcid is not None:
                name = bare(entity.dcid)
            elif entity.id is not None:
                name = entity.id
            else:
                continue
            predicate_names.setdefault(entity.qid, name)
            property_claimants.setdefault(name, []).append(entity.qid)

        properties_by_name = {
            name: qids[0] for name, qids in property_claimants.items()
        }

        return cls(
            entities=indexed,
            by_id=by_id,
            by_dcid=by_dcid,
            predicate_names=predicate_names,
            properties_by_name=properties_by_name,
            property_claimants=property_claimants,
            id_property=id_property,
            dcid_property=dcid_property,
            prefix=prefix,
            findings=tuple(findings),
        )

    def entity(self, qid: str) -> Entity | None:
        """Look up an entity by qid."""
        return self.entities.get(qid)

    def entity_by_id(self, id: str) -> Entity | None:
        """Look up the first entity claiming this dfo id."""
        qids = self.by_id.get(id)
        return self.entities[qids[0]] if qids else None

    def entity_by_dcid(self, dcid: str) -> Entity | None:
        """Look up the first entity claiming this dcid."""
        qids = self.by_dcid.get(dcid)
        return self.entities[qids[0]] if qids else None

    def property_named(self, name: str) -> Entity | None:
        """Look up the property entity discovered to claim this bare predicate name."""
        qid = self.properties_by_name.get(name)
        return self.entities[qid] if qid is not None else None

    def properties_named(self, name: str) -> list[Entity]:
        """Every property entity claiming this bare predicate name, in qid order."""
        return [self.entities[qid] for qid in self.property_claimants.get(name, [])]

    def statements(self, entity: Entity) -> list[Statement]:
        """This entity's claims as statements, excluding the two bookkeeping properties."""
        result = []
        for property_qid, values in entity.claims.items():
            if property_qid in (self.id_property, self.dcid_property):
                continue
            predicate = self.predicate_names.get(property_qid, property_qid)
            for value in values:
                result.append(
                    Statement(property=property_qid, predicate=predicate, value=value)
                )
        return result

    def values(self, entity: Entity, predicate: str) -> list[Value]:
        """Values stated through the property claiming this bare predicate."""
        property_qid = self.properties_by_name.get(predicate, predicate)
        return list(entity.claims.get(property_qid, []))

    def resolved(self, entity: Entity, predicate: str) -> Iterator[tuple[Ref, Entity]]:
        """Yield (ref, target) pairs for values that resolve to a known entity."""
        for value in self.values(entity, predicate):
            if isinstance(value, Ref):
                target = self.entities.get(value.qid)
                if target is not None:
                    yield value, target

    def dangling(self, entity: Entity) -> list[tuple[str, Ref]]:
        """(predicate, ref) pairs among this entity's statements resolving to nothing."""
        return [
            (statement.predicate, statement.value)
            for statement in self.statements(entity)
            if isinstance(statement.value, Ref)
            and statement.value.qid not in self.entities
        ]

    def defined(self) -> list[Entity]:
        """id-carrying entities, sorted by id."""
        return sorted(
            (e for e in self.entities.values() if e.id is not None),
            key=lambda e: e.id or "",
        )

    def references(self) -> list[Entity]:
        """dcid-carrying entities, sorted by dcid."""
        return sorted(
            (e for e in self.entities.values() if e.dcid is not None),
            key=lambda e: e.dcid or "",
        )

    def emitted_predicate(self, property_qid: str) -> str:
        """The MCF predicate this property qid renders as when emitted.

        Always bare: MCF property labels carry no namespace prefix — only
        values on the right-hand side do.
        """
        entity = self.entities[property_qid]
        if entity.dcid is not None:
            return bare(entity.dcid)
        return entity.id or property_qid

    def predicate_label(self, key: str) -> str:
        """Bare predicate name for a known property qid, else the key unchanged."""
        return self.predicate_names.get(key, key)


def target_text(graph: Graph, target: Entity | None, *, fallback: str) -> str:
    """Render a resolved target as MCF text: its id, else its dcid, else a fallback.

    Shared by emit.py (rendering a statement's value) and rules/graph.py
    (rendering a target inside a Finding message), so the two stay in sync.

    Args:
        graph: the graph providing the minted namespace prefix.
        target: the resolved entity, or None when it did not resolve.
        fallback: text to use when the target is None or carries neither id nor dcid.
    """
    if target is not None and target.id is not None:
        return f"{graph.prefix}:{target.id}"
    if target is not None and target.dcid is not None:
        return target.dcid
    return fallback


def escape(text: str) -> str:
    """Escape double quotes for MCF, the one place quoting happens."""
    return text.replace('"', '\\"')
