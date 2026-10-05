"""Read the Wikibase instance into a Graph: fetch the entities, then parse them.

The only module that touches the network, and it is GET-only and credential-free:
the compiler cannot write to the instance because no code here can. Never add
POST, login, token, or edit code.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import httpx

from dfo_ontology.config import PAGE_LIMIT, Config
from dfo_ontology.model import Entity, Finding, Graph, Kind, Literal, Ref, Value


class BenchError(RuntimeError):
    """A Wikibase API error payload, or an unusable response."""


# --- Fetching -------------------------------------------------------------


def fetch_entities(
    *, config: Config, transport: httpx.BaseTransport | None = None
) -> list[dict[str, Any]]:
    """Enumerate both namespaces and fetch every entity, returned sorted by qid.

    Args:
        config: connection, namespaces, and batching settings.
        transport: transport override for tests; defaults to a retrying HTTPTransport.
    """
    with httpx.Client(
        transport=transport or httpx.HTTPTransport(retries=3),
        timeout=30.0,
    ) as client:
        ids: list[str] = []
        for namespace in config.namespaces:
            ids.extend(
                entity_ids(
                    client, url=config.url, namespace=namespace, limit=PAGE_LIMIT
                )
            )
        payloads: list[dict[str, Any]] = []
        for start in range(0, len(ids), config.batch_size):
            batch = ids[start : start + config.batch_size]
            payloads.extend(fetch_batch(client, url=config.url, ids=batch))
    return sorted(payloads, key=lambda payload: payload["id"])


def entity_ids(
    client: httpx.Client, *, url: str, namespace: int, limit: int
) -> list[str]:
    """Enumerate this namespace's entity ids via allpages, following apcontinue.

    Args:
        client: the HTTP client.
        url: the instance's api.php endpoint.
        namespace: the MediaWiki namespace to list (item or property).
        limit: aplimit per page.
    """
    ids: list[str] = []
    apcontinue: str | None = None
    while True:
        params: dict[str, Any] = {
            "action": "query",
            "list": "allpages",
            "apnamespace": namespace,
            "apfilterredir": "nonredirects",
            "aplimit": limit,
            "format": "json",
            "formatversion": 2,
        }
        if apcontinue is not None:
            params["apcontinue"] = apcontinue
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        _raise_on_error(payload)
        for page in payload["query"]["allpages"]:
            ids.append(page["title"].split(":", 1)[-1])
        apcontinue = payload.get("continue", {}).get("apcontinue")
        if apcontinue is None:
            return ids


def fetch_batch(
    client: httpx.Client, *, url: str, ids: Sequence[str]
) -> list[dict[str, Any]]:
    """Fetch one wbgetentities batch (at most config.batch_size ids).

    Args:
        client: the HTTP client.
        url: the instance's api.php endpoint.
        ids: entity ids to fetch, joined with "|".
    """
    params = {
        "action": "wbgetentities",
        "ids": "|".join(ids),
        "props": "labels|descriptions|aliases|claims",
        "languages": "en",
        "format": "json",
        "formatversion": 2,
    }
    response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    _raise_on_error(payload)
    return list(payload["entities"].values())


def _raise_on_error(payload: Mapping[str, Any]) -> None:
    """Raise BenchError when the payload carries a top-level API error."""
    error = payload.get("error")
    if error is not None:
        raise BenchError(f"{error.get('code')}: {error.get('info')}")


# --- Parsing --------------------------------------------------------------


def read(payloads: Iterable[Mapping[str, Any]], *, config: Config) -> Graph:
    """Parse wbgetentities payloads into a Graph, accumulating R1-R3 findings.

    Args:
        payloads: one dict per entity, as returned by fetch_entities.
        config: bookkeeping property ids and the namespace prefix.
    """
    entities: list[Entity] = []
    findings: list[Finding] = []
    for payload in payloads:
        entity, entity_findings = parse_entity(payload, config=config)
        if entity is not None:
            entities.append(entity)
        findings.extend(entity_findings)

    findings.sort(
        key=lambda finding: (finding.rule, finding.value or "", finding.predicate or "")
    )

    return Graph.build(
        entities,
        id_property=config.id_property,
        dcid_property=config.dcid_property,
        prefix=config.prefix,
        findings=findings,
    )


def parse_entity(
    payload: Mapping[str, Any], *, config: Config
) -> tuple[Entity | None, list[Finding]]:
    """Parse one payload into an Entity, or None with a finding when it is unusable.

    Args:
        payload: one wbgetentities entity dict.
        config: bookkeeping property ids used to lift id/dcid onto the entity.
    """
    qid = payload.get("id")
    if "missing" in payload:
        return None, [
            Finding(rule="R3", value=qid, message="entity is missing from the bench")
        ]

    kind_name = payload.get("type")
    kind = Kind(kind_name) if kind_name is not None else _kind_from_qid(qid)

    label = payload.get("labels", {}).get("en", {}).get("value")
    description = payload.get("descriptions", {}).get("en", {}).get("value")
    aliases = tuple(a["value"] for a in payload.get("aliases", {}).get("en", []))

    entity = Entity(
        qid=qid, kind=kind, label=label, description=description, aliases=aliases
    )

    claims: dict[str, list[Value]] = {}
    findings: list[Finding] = []
    for property_qid, snaks in payload.get("claims", {}).items():
        for snak_wrapper in snaks:
            snak = snak_wrapper["mainsnak"]
            if snak["snaktype"] != "value":
                findings.append(
                    Finding(
                        rule="R1",
                        entity=entity,
                        predicate=property_qid,
                        message="statement carries no value (novalue/somevalue)",
                    )
                )
                continue
            value = _parse_datavalue(snak["datavalue"])
            if value is None:
                findings.append(
                    Finding(
                        rule="R2",
                        entity=entity,
                        predicate=property_qid,
                        message=f"unsupported datavalue type {snak['datavalue']['type']!r}",
                    )
                )
                continue
            claims.setdefault(property_qid, []).append(value)
    entity.claims = claims

    entity.id = _first_literal(claims, config.id_property)
    entity.dcid = _first_literal(claims, config.dcid_property)

    return entity, findings


def _kind_from_qid(qid: str | None) -> Kind:
    """Fall back to Kind.PROPERTY for a P-id, Kind.ITEM otherwise."""
    if qid is not None and qid.startswith("P"):
        return Kind.PROPERTY
    return Kind.ITEM


_ENTITY_TYPE_PREFIX = {"item": "Q", "property": "P"}


def _parse_datavalue(datavalue: Mapping[str, Any]) -> Value | None:
    """Turn one snak datavalue into a Ref or Literal, or None when unsupported."""
    value_type = datavalue.get("type")
    if value_type == "wikibase-entityid":
        value = datavalue["value"]
        qid = value.get("id")
        if qid is None:
            prefix = _ENTITY_TYPE_PREFIX.get(value["entity-type"])
            if prefix is None:
                return None
            qid = f"{prefix}{value['numeric-id']}"
        return Ref(qid)
    if value_type == "string":
        return Literal(datavalue["value"])
    return None


def _first_literal(claims: Mapping[str, list[Value]], property_qid: str) -> str | None:
    """The text of the first Literal statement made through this property, if any."""
    values = claims.get(property_qid)
    if values and isinstance(values[0], Literal):
        return values[0].text
    return None
