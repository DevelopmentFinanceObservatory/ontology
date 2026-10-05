"""Tests for reader.py — fetching over MockTransport and payload parsing."""

import httpx
import pytest

from dfo_ontology import reader
from dfo_ontology.config import Config
from dfo_ontology.model import Kind, Literal, Ref

CONFIG = Config(bench="testing")


def _snak(property_qid: str, datavalue: dict) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": property_qid,
            "datavalue": datavalue,
        }
    }


def _entity_ref(qid: str) -> dict:
    return {"entity-type": "item", "numeric-id": int(qid[1:]), "id": qid}


def test_parse_entity_labels_descriptions_aliases() -> None:
    """English label/description/aliases are lifted in payload order."""
    payload = {
        "id": "Q10",
        "type": "item",
        "labels": {"en": {"value": "financing activity"}},
        "descriptions": {"en": {"value": "an activity"}},
        "aliases": {"en": [{"value": "fin activity"}, {"value": "activity"}]},
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert findings == []
    assert entity is not None
    assert entity.label == "financing activity"
    assert entity.description == "an activity"
    assert entity.aliases == ("fin activity", "activity")


def test_parse_entity_kind_falls_back_to_qid() -> None:
    """A payload with no `type` key falls back to the qid's first letter."""
    entity, _ = reader.parse_entity({"id": "P9"}, config=CONFIG)
    assert entity is not None
    assert entity.kind is Kind.PROPERTY
    entity, _ = reader.parse_entity({"id": "Q9"}, config=CONFIG)
    assert entity is not None
    assert entity.kind is Kind.ITEM


def test_parse_entity_ref_and_literal_values() -> None:
    """wikibase-entityid becomes a Ref, string becomes a Literal."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {
            "P6": [
                _snak(
                    "P6",
                    {"type": "wikibase-entityid", "value": _entity_ref("Q11")},
                )
            ],
            "P1": [_snak("P1", {"type": "string", "value": "FinancingActivity"})],
        },
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert findings == []
    assert entity is not None
    assert entity.claims["P6"] == [Ref("Q11")]
    assert entity.claims["P1"] == [Literal("FinancingActivity")]


def test_parse_entity_entityid_composed_when_id_absent() -> None:
    """A wikibase-entityid value with no `id` maps entity-type to its real prefix."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {
            "P6": [
                _snak(
                    "P6",
                    {
                        "type": "wikibase-entityid",
                        "value": {"entity-type": "item", "numeric-id": 11},
                    },
                )
            ]
        },
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert findings == []
    assert entity is not None
    assert entity.claims["P6"] == [Ref("Q11")]


def test_parse_entity_entityid_unknown_type_r2() -> None:
    """A wikibase-entityid with an unrecognised entity-type and no `id` is R2, not guessed."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {
            "P6": [
                _snak(
                    "P6",
                    {
                        "type": "wikibase-entityid",
                        "value": {"entity-type": "unknown-thing", "numeric-id": 11},
                    },
                )
            ]
        },
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert entity is not None
    assert "P6" not in entity.claims
    assert len(findings) == 1
    assert findings[0].rule == "R2"
    assert findings[0].predicate == "P6"


def test_parse_entity_lifts_id_and_dcid_but_keeps_statements() -> None:
    """id/dcid land on the entity fields, and the statements stay in claims."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {
            "P1": [_snak("P1", {"type": "string", "value": "FinancingActivity"})],
            "P2": [_snak("P2", {"type": "string", "value": "schema:Thing"})],
        },
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert findings == []
    assert entity is not None
    assert entity.id == "FinancingActivity"
    assert entity.dcid == "schema:Thing"
    assert entity.claims["P1"] == [Literal("FinancingActivity")]
    assert entity.claims["P2"] == [Literal("schema:Thing")]


def test_parse_entity_r1_novalue_dropped() -> None:
    """A novalue/somevalue snak is dropped and reported as R1."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {"P6": [{"mainsnak": {"snaktype": "novalue", "property": "P6"}}]},
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert entity is not None
    assert "P6" not in entity.claims
    assert len(findings) == 1
    assert findings[0].rule == "R1"
    assert findings[0].predicate == "P6"
    assert findings[0].entity is entity


def test_parse_entity_r2_unsupported_datavalue() -> None:
    """A quantity or time datavalue is dropped and reported as R2."""
    payload = {
        "id": "Q10",
        "type": "item",
        "claims": {
            "P6": [_snak("P6", {"type": "quantity", "value": {"amount": "+1"}})],
            "P7": [_snak("P7", {"type": "time", "value": {"time": "+2026"}})],
        },
    }
    entity, findings = reader.parse_entity(payload, config=CONFIG)
    assert entity is not None
    assert entity.claims == {}
    assert {f.rule for f in findings} == {"R2"}
    assert {f.predicate for f in findings} == {"P6", "P7"}


def test_parse_entity_r3_missing() -> None:
    """An entry marked missing (key presence, not value) yields no entity and one R3."""
    entity, findings = reader.parse_entity(
        {"id": "Q99999", "missing": ""}, config=CONFIG
    )
    assert entity is None
    assert findings == [
        reader.Finding(rule="R3", value="Q99999", message=findings[0].message)
    ]


def test_read_returns_graph_with_sorted_findings() -> None:
    """read() builds a Graph and sorts findings so payload order cannot leak."""
    payloads = [
        {"id": "Q2", "missing": ""},
        {"id": "Q1", "missing": ""},
        {
            "id": "Q10",
            "type": "item",
            "claims": {"P6": [{"mainsnak": {"snaktype": "novalue", "property": "P6"}}]},
        },
    ]
    graph = reader.read(payloads, config=CONFIG)
    assert list(graph.entities) == ["Q10"]
    assert [f.rule for f in graph.findings] == ["R1", "R3", "R3"]
    assert [f.value for f in graph.findings if f.rule == "R3"] == ["Q1", "Q2"]


# --- Fetching ---------------------------------------------------------------


BASE_URL = "https://reader.test/w/api.php"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_entity_ids_pages_across_apcontinue() -> None:
    """entity_ids follows continue.apcontinue until it is absent."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "apcontinue" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "continue": {"apcontinue": "Q3"},
                    "query": {"allpages": [{"title": "Item:Q1"}, {"title": "Item:Q2"}]},
                },
            )
        return httpx.Response(200, json={"query": {"allpages": [{"title": "Item:Q3"}]}})

    ids = reader.entity_ids(_client(handler), url=BASE_URL, namespace=120, limit=500)
    assert ids == ["Q1", "Q2", "Q3"]
    assert len(calls) == 2


def test_fetch_entities_batches_at_boundary() -> None:
    """13 ids at batch_size 5 make 3 wbgetentities calls."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.params.get("action") == "query":
            titles = [f"Item:Q{i}" for i in range(1, 14)]
            return httpx.Response(
                200, json={"query": {"allpages": [{"title": t} for t in titles]}}
            )
        ids = request.url.params["ids"].split("|")
        return httpx.Response(200, json={"entities": {qid: {"id": qid} for qid in ids}})

    config = Config(bench="testing", namespaces=(120,), batch_size=5)
    payloads = reader.fetch_entities(
        config=config, transport=httpx.MockTransport(handler)
    )
    assert [p["id"] for p in payloads] == sorted(f"Q{i}" for i in range(1, 14))
    wbgetentities_calls = [
        c for c in calls if c.url.params.get("action") == "wbgetentities"
    ]
    assert len(wbgetentities_calls) == 3
    assert [len(c.url.params["ids"].split("|")) for c in wbgetentities_calls] == [
        5,
        5,
        3,
    ]


def test_error_payload_raises_bench_error() -> None:
    """A top-level `error` key raises BenchError naming the code and info."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": {"code": "no-such-entity", "info": "bad id"}}
        )

    with pytest.raises(reader.BenchError, match="no-such-entity: bad id"):
        reader.fetch_batch(_client(handler), url=BASE_URL, ids=["Q1"])


def test_500_raises_http_status_error() -> None:
    """A 500 response raises httpx.HTTPStatusError rather than being swallowed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    with pytest.raises(httpx.HTTPStatusError):
        reader.fetch_batch(_client(handler), url=BASE_URL, ids=["Q1"])


def test_every_request_is_a_get() -> None:
    """The read-only guard: no request reader.py issues is ever anything but GET."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.params.get("action") == "query":
            return httpx.Response(
                200, json={"query": {"allpages": [{"title": "Item:Q1"}]}}
            )
        return httpx.Response(200, json={"entities": {"Q1": {"id": "Q1"}}})

    config = Config(bench="testing", namespaces=(120, 122))
    reader.fetch_entities(config=config, transport=httpx.MockTransport(handler))
    assert calls
    assert all(call.method == "GET" for call in calls)


def test_fetch_batch_missing_entry_included() -> None:
    """A missing entry (marked by key presence, not value) is returned, not dropped."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"entities": {"Q99999": {"id": "Q99999", "missing": ""}}},
        )

    payloads = reader.fetch_batch(_client(handler), url=BASE_URL, ids=["Q99999"])
    assert payloads == [{"id": "Q99999", "missing": ""}]
