"""Seam test: reader -> validate -> emit -> report over one inline wbgetentities fixture.

The fixture is shaped the way the live bench actually returns it (formatversion=2,
claims keyed by property id, snaks carrying `datavalue.value`) rather than built through
`tests/graphbuild.py`, which no rule-level test exercises: the qid indirection, the
discovered predicate map, the id/dcid lift, bookkeeping exclusion, and the injected
`schema:Property` all live between reader and emit, and only this test crosses all four
modules in one pipeline.
"""

from dfo_ontology import codes, emit, reader, report, validate
from dfo_ontology.config import Config

CONFIG = Config(bench="dev")


def _snak(property_qid: str, datavalue: dict) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": property_qid,
            "datavalue": datavalue,
        }
    }


def _string(property_qid: str, text: str) -> dict:
    return _snak(property_qid, {"type": "string", "value": text})


def _entity_ref(property_qid: str, qid: str) -> dict:
    entity_type = "item" if qid.startswith("Q") else "property"
    value = {"entity-type": entity_type, "numeric-id": int(qid[1:]), "id": qid}
    return _snak(property_qid, {"type": "wikibase-entityid", "value": value})


def _labels(en: str) -> dict:
    return {"en": {"language": "en", "value": en}}


# The live bench's bookkeeping properties, carrying no identifier of their own.
PAYLOADS: list[dict] = [
    {"id": "P1", "type": "property"},
    {"id": "P2", "type": "property"},
    # The four structural properties the fixture's statements are made through.
    {"id": "P3", "type": "property", "claims": {"P2": [_string("P2", "dcid:typeOf")]}},
    {
        "id": "P4",
        "type": "property",
        "claims": {"P2": [_string("P2", "dcid:subClassOf")]},
    },
    {
        "id": "P6",
        "type": "property",
        "claims": {"P2": [_string("P2", "dcid:domainIncludes")]},
    },
    {
        "id": "P7",
        "type": "property",
        "claims": {"P2": [_string("P2", "dcid:rangeIncludes")]},
    },
    # The four reference items, each locally typed Class through the same well-known.
    {
        "id": "Q1",
        "type": "item",
        "claims": {
            "P2": [_string("P2", "schema:Class")],
            "P3": [_entity_ref("P3", "Q1")],
        },
    },
    {
        "id": "Q2",
        "type": "item",
        "claims": {
            "P2": [_string("P2", "schema:Property")],
            "P3": [_entity_ref("P3", "Q1")],
        },
    },
    {
        "id": "Q3",
        "type": "item",
        "claims": {
            "P2": [_string("P2", "schema:Enumeration")],
            "P3": [_entity_ref("P3", "Q1")],
        },
    },
    {
        "id": "Q4",
        "type": "item",
        "claims": {
            "P2": [_string("P2", "schema:Thing")],
            "P3": [_entity_ref("P3", "Q1")],
        },
    },
    # A class, a value list, a value, and a minted property.
    {
        "id": "Q10",
        "type": "item",
        "labels": _labels("financing activity"),
        "descriptions": _labels(
            "An activity that moves development finance from one party to another."
        ),
        "claims": {
            "P1": [_string("P1", "FinancingActivity")],
            "P3": [_entity_ref("P3", "Q1")],
            "P4": [_entity_ref("P4", "Q4")],
        },
    },
    {
        "id": "Q11",
        "type": "item",
        "labels": _labels("financing purpose (value list)"),
        "descriptions": _labels(
            "The list of values used to classify financing activities by purpose."
        ),
        "claims": {
            "P1": [_string("P1", "FinancingPurposeEnum")],
            "P3": [_entity_ref("P3", "Q1")],
            "P4": [_entity_ref("P4", "Q3")],
        },
    },
    {
        "id": "Q12",
        "type": "item",
        "labels": _labels("basic health (CRS purpose)"),
        "descriptions": _labels("Financing whose purpose is basic health services."),
        "aliases": {"en": [{"language": "en", "value": "basic health"}]},
        "claims": {
            "P1": [_string("P1", "CRSPurposeBasicHealth")],
            "P3": [_entity_ref("P3", "Q11")],
        },
    },
    {
        "id": "P9",
        "type": "property",
        "labels": _labels("financing purpose"),
        "descriptions": _labels(
            "The purpose classification stated on a financing activity."
        ),
        "claims": {
            "P1": [_string("P1", "financingPurpose")],
            "P6": [_entity_ref("P6", "Q10")],
            "P7": [_entity_ref("P7", "Q11")],
        },
    },
]

EXPECTED_MCF = (
    "# bench: dev (https://dfo-dev.wikibase.cloud)\n"
    "\n"
    "Node: dcid:FinancingActivity\n"
    "typeOf: schema:Class\n"
    'name: "financing activity"\n'
    'description: "An activity that moves development finance from one party '
    'to another."\n'
    "subClassOf: schema:Thing\n"
    "\n"
    "Node: dcid:FinancingPurposeEnum\n"
    "typeOf: schema:Class\n"
    'name: "financing purpose (value list)"\n'
    'description: "The list of values used to classify financing activities '
    'by purpose."\n'
    "subClassOf: schema:Enumeration\n"
    "\n"
    "Node: dcid:CRSPurposeBasicHealth\n"
    "typeOf: dcid:FinancingPurposeEnum\n"
    'name: "basic health (CRS purpose)"\n'
    'description: "Financing whose purpose is basic health services."\n'
    'alternateName: "basic health"\n'
    "\n"
    "Node: dcid:financingPurpose\n"
    "typeOf: schema:Property\n"
    'name: "financing purpose"\n'
    'description: "The purpose classification stated on a financing activity."\n'
    "domainIncludes: dcid:FinancingActivity\n"
    "rangeIncludes: dcid:FinancingPurposeEnum\n"
)

EXPECTED_REPORT = (
    "bench: dev (https://dfo-dev.wikibase.cloud)\n"
    "\n"
    "1 class, 1 property, 1 value list, 1 value, 0 individual\n"
    "8 reference entities emitted no node\n"
)


# Header-only: the fixture predates the classificationCode property.
EXPECTED_CODES = "list,code,dcid,label,property\n"


def compile_payloads(payloads: list[dict]) -> tuple[str, str, str]:
    """Run payloads through the whole pipeline, returning all three artifacts."""
    graph = reader.read(payloads, config=CONFIG)
    result = validate.validate(graph)
    return (
        emit.emit(graph, config=CONFIG),
        report.render(graph, result, config=CONFIG),
        codes.render(graph),
    )


def test_seam_produces_exact_mcf_report_and_codes() -> None:
    """The 14-entity fixture emits exactly four nodes and reports a clean success."""
    mcf, text, csv_text = compile_payloads(PAYLOADS)
    assert mcf == EXPECTED_MCF
    assert text == EXPECTED_REPORT
    assert csv_text == EXPECTED_CODES
