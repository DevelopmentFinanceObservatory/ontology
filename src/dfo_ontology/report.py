"""Renders report.txt: the failure or success form of a validation run.

`entity_header` is the only place an entity is named — shared by failure
groups, skip lines, and advisory lines, so a skip is identified exactly as
fully as an error.
"""

import re

from dfo_ontology import shapes
from dfo_ontology.codes import code_literals, subjects
from dfo_ontology.config import Config
from dfo_ontology.model import Entity, Finding, Graph, Result
from dfo_ontology.provisional import flagged
from dfo_ontology.shapes import Reach, Shape

FOOTER = "See docs/validation.md for what each rule id checks."

_RULE_ID = re.compile(r"([A-Za-z]+)(\d*)")


def _rule_sort_key(rule_id: str) -> tuple[str, int]:
    """Letter prefix, then numeric suffix, so I2 sorts before I10."""
    match = _RULE_ID.match(rule_id)
    if match is None:
        return (rule_id, 0)
    letters, digits = match.groups()
    return (letters, int(digits) if digits else 0)


def _header(n: int, m: int, c: int) -> str:
    """The count line: truthful whether errors are per-entity, cross-entity, or both.

    Args:
        n: total errors.
        m: per-entity groups.
        c: cross-entity findings, already counted in n.
    """
    error_word = f"error{'s' if n != 1 else ''}"
    if c and not m:
        return f"{n} {error_word}, all cross-entity"
    if c:
        per_entity = n - c
        return (
            f"{n} {error_word}: {per_entity} across "
            f"{m} entit{'ies' if m != 1 else 'y'}, {c} cross-entity"
        )
    return f"{n} {error_word} across {m} entit{'ies' if m != 1 else 'y'}"


def entity_header(entity: Entity) -> str:
    """Render `id or dcid — "label" (qid)`, dropping absent parts.

    Args:
        entity: the entity to name.
    """
    text = entity.id or entity.dcid or ""
    if entity.label is not None:
        label = f'"{entity.label}"'
        text = f"{text} — {label}" if text else label
    if entity.qid is not None:
        text = f"{text} ({entity.qid})" if text else f"({entity.qid})"
    return text


def _group_key(
    entity: Entity,
) -> tuple[int, str, int, int]:
    """The total order group findings by entity: id, then dcid, then neither."""
    if entity.id:
        bucket = 0
    elif entity.dcid:
        bucket = 1
    else:
        bucket = 2
    qid = entity.qid
    return (
        bucket,
        entity.id or entity.dcid or "",
        0 if qid else 1,
        int(qid[1:]) if qid else 0,
    )


def _finding_body(graph: Graph, finding: Finding) -> str:
    """`predicate → value: message`, degrading as parts are absent."""
    predicate = graph.predicate_label(finding.predicate) if finding.predicate else None
    prefix = " → ".join(part for part in (predicate, finding.value) if part)
    return f"{prefix}: {finding.message}" if prefix else finding.message


def _finding_sort_key(graph: Graph, finding: Finding) -> tuple[str, str, str]:
    """`(rule, predicate, value)`, rendering the predicate first."""
    predicate = graph.predicate_label(finding.predicate) if finding.predicate else ""
    return (finding.rule, predicate, finding.value or "")


def _group_findings(
    findings: list[Finding],
) -> tuple[dict[int, tuple[Entity, list[Finding]]], list[Finding]]:
    """Split findings into per-entity groups (keyed by object identity) and cross-entity."""
    groups: dict[int, tuple[Entity, list[Finding]]] = {}
    cross: list[Finding] = []
    for finding in findings:
        if finding.entity is None:
            cross.append(finding)
            continue
        key = id(finding.entity)
        if key not in groups:
            groups[key] = (finding.entity, [])
        groups[key][1].append(finding)
    return groups, cross


def _entity_sort_key(finding: Finding) -> tuple[int, str, int, int]:
    """Group key for a finding whose entity may be absent (sorts last)."""
    if finding.entity is None:
        return (3, "", 1, 0)
    return _group_key(finding.entity)


def _skip_lines(graph: Graph, skips: list[Finding]) -> list[str]:
    """One line per skip, each naming its entity in full."""
    ordered = sorted(
        skips,
        key=lambda f: (_entity_sort_key(f), *_finding_sort_key(graph, f)),
    )
    lines = []
    for finding in ordered:
        body = _finding_body(graph, finding)
        if finding.entity is not None:
            lines.append(f"  {finding.rule}  {entity_header(finding.entity)}  {body}")
        else:
            lines.append(f"  {finding.rule}  {body}")
    return lines


def _advisory_lines(graph: Graph, advisories: list[Finding]) -> list[str]:
    """One line per advisory: entity, then its message."""
    ordered = sorted(
        advisories,
        key=lambda f: (_entity_sort_key(f), f.rule),
    )
    lines = []
    for finding in ordered:
        header = entity_header(finding.entity) if finding.entity is not None else ""
        lines.append(f"  {finding.rule}  {header}: {finding.message}")
    return lines


def _code_coverage_lines(graph: Graph) -> list[str]:
    """One line per type holding a coded entity, naming any uncoded members.

    Coverage is information, not enforcement: a partially coded list renders
    here but never fails a run.
    """
    members: dict[str, tuple[Entity, list[Entity], list[Entity]]] = {}
    for entity in subjects(graph):
        target = shapes.type_target(graph, entity)
        if target is None:
            continue
        # Reference lists have no id, so the sort key falls back to the dcid.
        key = target.id or target.dcid or target.qid or ""
        _, coded, uncoded = members.setdefault(key, (target, [], []))
        has_code = bool(code_literals(graph, entity))
        (coded if has_code else uncoded).append(entity)

    lines: list[str] = []
    for _, (target, coded, uncoded) in sorted(members.items()):
        if not coded:
            continue
        total = len(coded) + len(uncoded)
        lines.append(f"  {entity_header(target)}: {len(coded)} of {total} coded")
        if uncoded:
            names = ", ".join(
                entity_header(e) for e in sorted(uncoded, key=lambda e: e.id or "")
            )
            lines.append(f"    uncoded: {names}")
    return lines


def _provisional_lines(graph: Graph) -> list[str]:
    """One line per provisional node, so a passing run says what is not final."""
    return [f"  {entity_header(e)}" for e in flagged(graph)]


def render(
    graph: Graph, result: Result, *, config: Config, exclude_provisional: bool = False
) -> str:
    """report.txt: the bench line, then the failure or success form per result.ok.

    Args:
        graph: the graph that was validated.
        result: the accumulated validation result.
        config: the bench the graph was read from.
        exclude_provisional: whether provisional nodes were left out of the MCF.
    """
    body = (
        success_report(graph, result, exclude_provisional=exclude_provisional)
        if result.ok
        else failure_report(graph, result)
    )
    return f"{config.provenance}\n\n{body}"


def failure_report(graph: Graph, result: Result) -> str:
    """Render the failure form: counts, per-entity groups, cross-entity, skips.

    Args:
        graph: the graph that was validated.
        result: the accumulated validation result.
    """
    groups, cross = _group_findings(result.errors)
    n = len(result.errors)
    m = len(groups)
    c = len(cross)
    lines = [_header(n, m, c)]
    if result.not_run:
        lines.append(
            f"Not run: {', '.join(sorted(result.not_run, key=_rule_sort_key))}"
        )

    for entity, findings in sorted(
        groups.values(), key=lambda pair: _group_key(pair[0])
    ):
        lines.append("")
        lines.append(entity_header(entity))
        for finding in sorted(findings, key=lambda f: _finding_sort_key(graph, f)):
            lines.append(f"  {finding.rule}  {_finding_body(graph, finding)}")

    if cross:
        lines.append("")
        lines.append("Cross-entity")
        for finding in sorted(cross, key=lambda f: (f.rule, f.message, f.value or "")):
            lines.append(f"  {finding.rule}  {_finding_body(graph, finding)}")

    skip_lines = _skip_lines(graph, result.skips)
    if skip_lines:
        lines.append("")
        lines.append("Skipped checks")
        lines.extend(skip_lines)

    advisory_lines = _advisory_lines(graph, result.advisories)
    if advisory_lines:
        lines.append("")
        lines.append("Advisories")
        lines.extend(advisory_lines)

    lines.append("")
    lines.append(FOOTER)
    return "\n".join(lines) + "\n"


def success_report(
    graph: Graph, result: Result, *, exclude_provisional: bool = False
) -> str:
    """Render the success form: counts, codes, provisional nodes, skips, advisories.

    Args:
        graph: the graph that was validated.
        result: the accumulated validation result.
        exclude_provisional: whether provisional nodes were left out of the MCF.
    """
    n_class = n_property = n_value_list = n_value = n_individual = 0
    n_indeterminate = 0
    for entity in graph.defined():
        dispatch = shapes.dispatch(graph, entity)
        if dispatch.shape in (Shape.MINTED_PROPERTY, Shape.CONSTRAINT_PROPERTY):
            n_property += 1
        elif dispatch.shape is Shape.CLASS_OR_LIST:
            if shapes.reach(graph, entity) is Reach.ENUMERATION:
                n_value_list += 1
            else:
                n_class += 1
        elif dispatch.shape is Shape.VALUE:
            n_value += 1
        elif dispatch.shape is Shape.INDIVIDUAL:
            n_individual += 1
        elif dispatch.shape is Shape.VALUE_OR_INDIVIDUAL:
            n_indeterminate += 1

    counts = (
        f"{n_class} class, {n_property} property, {n_value_list} value list, "
        f"{n_value} value, {n_individual} individual"
    )
    if n_indeterminate:
        counts += f", {n_indeterminate} indeterminate"

    refs = len(graph.references())
    lines = [
        counts,
        f"{refs} reference entit{'ies' if refs != 1 else 'y'} emitted no node",
    ]

    coverage = _code_coverage_lines(graph)
    if coverage:
        lines.append("")
        lines.append("Codes")
        lines.extend(coverage)

    provisional = _provisional_lines(graph)
    if provisional:
        lines.append("")
        where = "left out of" if exclude_provisional else "included in"
        lines.append(f"Provisional ({len(provisional)}), {where} the MCF and codes.csv")
        lines.extend(provisional)

    footer_needed = False
    skip_lines = _skip_lines(graph, result.skips)
    if skip_lines:
        lines.append("")
        lines.append("Skipped checks")
        lines.extend(skip_lines)
        footer_needed = True

    advisory_lines = _advisory_lines(graph, result.advisories)
    if advisory_lines:
        lines.append("")
        lines.append("Advisories")
        lines.extend(advisory_lines)
        footer_needed = True

    if footer_needed:
        lines.append("")
        lines.append(FOOTER)

    return "\n".join(lines) + "\n"
