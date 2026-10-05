"""Tests for codes.py. Graphs are built directly; no validator run."""

from dfo_ontology import codes, provisional
from dfo_ontology.model import Kind

from .graphbuild import bench_vocab, entity, graph, lit, ref

CODE_PROP = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
DAC_PROP = entity("P41", kind=Kind.PROPERTY, id="dacCode")
ISO_PROP = entity("P42", kind=Kind.PROPERTY, id="iso4217AlphaCode")
FRUIT_ENUM = entity(
    "Q90",
    id="FruitEnum",
    label="fruit",
    description="d",
    claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
)


def _value(qid: str, id: str, label: str | None, code: str, list_qid: str = "Q90"):
    return entity(
        qid,
        id=id,
        label=label,
        description="d",
        claims={"P3": [ref(list_qid)], "P40": [lit(code)]},
    )


def test_rows_sorted_by_list_then_code() -> None:
    """Rows across two lists come out sorted by (list, code), header first."""
    veg_enum = entity(
        "Q95",
        id="VegEnum",
        label="veg",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        veg_enum,
        _value("Q96", "Carrot", "carrot", "CAR", list_qid="Q95"),
        FRUIT_ENUM,
        _value("Q92", "Banana", "banana", "BAN"),
        _value("Q91", "Apple", "apple", "APL"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:FruitEnum,APL,dcid:Apple,apple,classificationCode\n"
        "dcid:FruitEnum,BAN,dcid:Banana,banana,classificationCode\n"
        "dcid:VegEnum,CAR,dcid:Carrot,carrot,classificationCode\n"
    )


def test_columns_follow_the_graph_prefix() -> None:
    """Both prefixed columns — the list and the row's own dcid — read the graph's
    prefix, so neither bakes in whichever namespace we currently mint under."""
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        FRUIT_ENUM,
        _value("Q91", "Apple", "apple", "APL"),
        prefix="example",
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "example:FruitEnum,APL,example:Apple,apple,classificationCode\n"
    )


def test_label_with_comma_is_quoted() -> None:
    """A label containing a comma is quoted, nothing else is."""
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        FRUIT_ENUM,
        _value("Q91", "Apple", "apple, cored", "APL"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        'dcid:FruitEnum,APL,dcid:Apple,"apple, cored",classificationCode\n'
    )


def test_no_codes_renders_the_header_only() -> None:
    """A graph without codes still renders the header line."""
    assert codes.render(graph(*bench_vocab())) == "list,code,dcid,label,property\n"


def test_reference_list_is_named_by_its_own_dcid() -> None:
    """A value typed to a reference names the global node, prefix and all.

    The reference has no id of ours, but it is still the set the code was
    assigned in, which is what a consumer filters by.
    """
    reference_list = entity("Q97", dcid="dcs:CRSPurposeEnum")
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        reference_list,
        _value("Q91", "Apple", "apple", "APL", list_qid="Q97"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcs:CRSPurposeEnum,APL,dcid:Apple,apple,classificationCode\n"
    )


def test_missing_label_renders_an_empty_cell() -> None:
    """A value without a label gets an empty label cell, not a crash."""
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        FRUIT_ENUM,
        _value("Q91", "Apple", None, "APL"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:FruitEnum,APL,dcid:Apple,,classificationCode\n"
    )


def _org_class(id: str = "SomeClass", label: str = "some class"):
    """A minted class under Thing — what an individual is typed to."""
    return entity(
        "Q93",
        id=id,
        label=label,
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )


def _individual(code: str = "913", list_qid: str = "Q93"):
    """An individual carrying one dacCode."""
    return entity(
        "Q94",
        id="SomeOrg",
        label="some org",
        description="d",
        claims={"P3": [ref(list_qid)], "P41": [lit(code)]},
    )


def test_daccode_rows_join_the_csv() -> None:
    """Individuals coded through dacCode render rows naming their class."""
    g = graph(*bench_vocab(), DAC_PROP, _org_class(), _individual())
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:SomeClass,913,dcid:SomeOrg,some org,dacCode\n"
    )


def test_m49_code_reaches_codes_csv() -> None:
    """A grouping's M49 code renders a row, naming the scheme class it sits in."""
    m49 = entity("P43", kind=Kind.PROPERTY, id="m49Code")
    grouping = entity(
        "Q95",
        id="M49NorthernAfrica",
        label="Northern Africa (UN M49)",
        description="d",
        claims={"P3": [ref("Q93")], "P43": [lit("015")]},
    )
    g = graph(*bench_vocab(), m49, _org_class("M49SubRegion"), grouping)
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:M49SubRegion,015,dcid:M49NorthernAfrica,Northern Africa (UN M49),m49Code\n"
    )


def test_a_currency_renders_a_row_per_register_it_belongs_to() -> None:
    """Codes from two registers on one entity render a row each, one dcid.

    This is what lets a consumer join on whichever code its source carries.
    """
    currency = entity(
        "Q94",
        id="CurrencyCHF",
        label="Swiss Franc",
        description="d",
        claims={
            "P3": [ref("Q93")],
            "P41": [lit("11"), lit("70")],
            "P42": [lit("CHF")],
        },
    )
    g = graph(*bench_vocab(), DAC_PROP, ISO_PROP, _org_class("CurrencyUnit"), currency)
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:CurrencyUnit,11,dcid:CurrencyCHF,Swiss Franc,dacCode\n"
        "dcid:CurrencyUnit,70,dcid:CurrencyCHF,Swiss Franc,dacCode\n"
        "dcid:CurrencyUnit,CHF,dcid:CurrencyCHF,Swiss Franc,iso4217AlphaCode\n"
    )


def test_daccode_row_typed_to_a_reference_names_the_reference() -> None:
    """A class that is a reference fills the column with the dcid it carries.

    Without it two entities of different classes sharing a register code would
    be indistinguishable in the file.
    """
    organization = entity(
        "Q93",
        dcid="dcid:Organization",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    g = graph(*bench_vocab(), DAC_PROP, organization, _individual())
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:Organization,913,dcid:SomeOrg,some org,dacCode\n"
    )


def test_daccode_and_classification_rows_sort_together() -> None:
    """Rows from both code properties come out in one (list, code) order."""
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        DAC_PROP,
        _org_class("AClass", "a class"),
        _individual(),
        FRUIT_ENUM,
        _value("Q91", "Apple", "apple", "APL"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:AClass,913,dcid:SomeOrg,some org,dacCode\n"
        "dcid:FruitEnum,APL,dcid:Apple,apple,classificationCode\n"
    )


def test_entity_order_does_not_change_the_output() -> None:
    """The same entities in reversed order render byte-identical CSV."""
    entities = [
        CODE_PROP,
        FRUIT_ENUM,
        _value("Q91", "Apple", "apple", "APL"),
        _value("Q92", "Banana", "banana", "BAN"),
    ]
    forward = codes.render(graph(*bench_vocab(), *entities))
    backward = codes.render(graph(*reversed(entities), *bench_vocab()))
    assert forward == backward


def test_minted_target_with_a_blind_chain_is_still_named() -> None:
    """A minted target names itself even when its own chain dead-ends.

    Whether the target is a value list or a class no longer decides the
    column: either way it is the set the code was assigned in.
    """
    bare = entity("Q98", dcid="dcs:SomeThing")
    blind_list = entity(
        "Q97",
        id="BlindEnum",
        label="blind",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q98")]},
    )
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        bare,
        blind_list,
        _value("Q91", "Apple", "apple", "APL", list_qid="Q97"),
    )
    assert codes.render(g) == (
        "list,code,dcid,label,property\n"
        "dcid:BlindEnum,APL,dcid:Apple,apple,classificationCode\n"
    )


def test_reference_codes_reach_codes_csv() -> None:
    """A reference's codes emit a row, keyed by the global dcid it points at.

    A reference emits no MCF node, so this row is the only thing it produces.
    Losing it would mean the pipeline could not resolve a source code at all.
    """
    country = entity(
        "Q20", dcid="dcid:Country", label="Country", claims={"P3": [ref("Q1")]}
    )
    afg = entity(
        "Q21",
        dcid="dcid:country/AFG",
        label="Afghanistan",
        claims={"P3": [ref("Q20")], "P41": [lit("625")]},
    )
    g = graph(*bench_vocab(), DAC_PROP, country, afg)
    assert codes.render(g).splitlines()[1:] == [
        "dcid:Country,625,dcid:country/AFG,Afghanistan,dacCode"
    ]


def test_reference_and_minted_codes_share_one_register() -> None:
    """The list column is what keeps two registers' identical codes apart."""
    country = entity(
        "Q20", dcid="dcid:Country", label="Country", claims={"P3": [ref("Q1")]}
    )
    austria = entity(
        "Q21",
        dcid="dcid:country/AUT",
        label="Austria",
        claims={"P3": [ref("Q20")], "P41": [lit("1")]},
    )
    units = entity(
        "Q30",
        id="CurrencyUnit",
        label="Currency",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    schilling = entity(
        "Q31",
        id="CurrencyATS",
        label="Schilling",
        description="d",
        claims={"P3": [ref("Q30")], "P41": [lit("1")]},
    )
    g = graph(*bench_vocab(), DAC_PROP, country, austria, units, schilling)
    assert codes.render(g).splitlines()[1:] == [
        "dcid:Country,1,dcid:country/AUT,Austria,dacCode",
        "dcid:CurrencyUnit,1,dcid:CurrencyATS,Schilling,dacCode",
    ]


def test_render_leaves_out_provisional_nodes_only_when_asked() -> None:
    """A provisional node's code row goes with the option, as its MCF node does."""
    flag = entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional")
    true = entity("Q30", dcid="schema:True")
    draft = entity(
        "Q91",
        id="Apple",
        label="apple",
        description="d",
        claims={"P3": [ref("Q90")], "P40": [lit("APL")], "P30": [ref("Q30")]},
    )
    g = graph(
        *bench_vocab(),
        CODE_PROP,
        flag,
        true,
        FRUIT_ENUM,
        draft,
        _value("Q92", "Banana", "banana", "BAN"),
    )
    assert "APL" in codes.render(g)
    excluded = codes.render(provisional.without(g))
    assert "APL" not in excluded
    assert "BAN" in excluded
