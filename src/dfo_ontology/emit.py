"""MCF text: one node per id-carrying entity, rendered deterministically."""

from dfo_ontology.config import Config
from dfo_ontology.model import Entity, Graph, Ref, Value, escape, target_text
from dfo_ontology.shapes import Shape, dispatch

STRUCTURAL_ORDER = (
    "subClassOf",
    "subPropertyOf",
    "domainIncludes",
    "rangeIncludes",
    "specializationOf",
)


def emit(graph: Graph, *, config: Config) -> str:
    """Render every id-carrying entity as MCF, one node per entity, deterministically.

    The file opens with a comment naming the bench it was compiled from, so an
    MCF that has travelled away from its report still says where it came from.
    Whole-line comments are legal MCF; trailing ones are not. The name and site
    only — a timestamp would break byte-identical output.

    Args:
        graph: the graph to render.
        config: the bench the graph was read from.
    """
    header = f"# {config.provenance}\n"
    order = emission_order(graph)
    if not order:
        return header
    body = "\n\n".join(node_text(graph, entity) for entity in order) + "\n"
    return f"{header}\n{body}"


def emission_order(graph: Graph) -> list[Entity]:
    """Kahn order over id-carrying entities, tie-broken alphabetically.

    Repeatedly emits the alphabetically smallest id whose dependencies — the
    ids of any id-carrying targets among its own statements, self excluded —
    are already emitted. A dcid-only reference target is never a dependency.
    G8 rejects a cycle in every hierarchy-forming predicate, so a graph that
    reaches emission has a valid order. If one somehow does not, the remaining
    ids are appended sorted and the loop stops rather than raising, keeping the
    output deterministic.

    Args:
        graph: the graph to order.
    """
    entities: dict[str, Entity] = {}
    for e in graph.defined():
        if e.id is not None:
            entities[e.id] = e
    pending: dict[str, set[str]] = {}
    for id_, entity in entities.items():
        deps: set[str] = set()
        for statement in graph.statements(entity):
            if isinstance(statement.value, Ref):
                target = graph.entity(statement.value.qid)
                if target is not None and target.id is not None and target.id != id_:
                    deps.add(target.id)
        pending[id_] = deps

    order: list[Entity] = []
    remaining = set(pending)
    while remaining:
        ready = sorted(i for i in remaining if not pending[i])
        if not ready:
            order.extend(entities[i] for i in sorted(remaining))
            break
        next_id = ready[0]
        order.append(entities[next_id])
        remaining.discard(next_id)
        for deps in pending.values():
            deps.discard(next_id)
    return order


def node_text(graph: Graph, entity: Entity) -> str:
    """Render one entity's MCF node text, statement order fixed by the rulebook.

    Args:
        graph: the graph the entity belongs to.
        entity: the id-carrying entity to render.
    """
    lines = [f"Node: {graph.prefix}:{entity.id}"]

    type_of: list[str] = []
    groups: dict[str, list[str]] = {}
    for statement in graph.statements(entity):
        predicate = graph.emitted_predicate(statement.property)
        rendered = render_value(graph, statement.value)
        if predicate == "typeOf":
            type_of.append(rendered)
            continue
        groups.setdefault(predicate, []).append(rendered)

    if dispatch(graph, entity).shape is Shape.MINTED_PROPERTY:
        type_of = ["schema:Property"]
    if type_of:
        lines.append(f"typeOf: {', '.join(type_of)}")

    if entity.label is not None:
        lines.append(f'name: "{escape(entity.label)}"')
    if entity.description is not None:
        lines.append(f'description: "{escape(entity.description)}"')
    if entity.aliases:
        aliases = ", ".join(f'"{escape(a)}"' for a in entity.aliases)
        lines.append(f"alternateName: {aliases}")

    for predicate in STRUCTURAL_ORDER:
        values = groups.pop(predicate, None)
        if values:
            lines.append(f"{predicate}: {', '.join(values)}")

    for predicate in sorted(groups):
        lines.append(f"{predicate}: {', '.join(groups[predicate])}")

    return "\n".join(lines)


def render_value(graph: Graph, value: Value) -> str:
    """Render one statement value as MCF text.

    Args:
        graph: the graph to resolve a `Ref` target against.
        value: the value to render.
    """
    if isinstance(value, Ref):
        target = graph.entity(value.qid)
        # Unreachable once G1 has passed; the fallback exists so that a target
        # which somehow did not resolve is still visible in the output.
        return target_text(graph, target, fallback=value.qid)
    return f'"{escape(value.text)}"'
