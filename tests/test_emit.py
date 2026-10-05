"""Tests for emit.py: node ordering, statement order, rendering, separators."""

from dfo_ontology import provisional
from dfo_ontology.config import PREFIX, Config
from dfo_ontology.emit import emission_order, emit, node_text, render_value
from dfo_ontology.model import Kind
from tests.graphbuild import bench_vocab, entity, graph, lit, ref

CONFIG = Config(bench="testing")
HEADER = "# bench: testing (https://dfo-testing-2.wikibase.cloud)\n"


def test_emission_order_chain_and_tiebreak() -> None:
    """A dependency chain resolves first; ready siblings tie-break alphabetically,
    with uppercase ids preceding lowercase ones."""
    g = graph(
        entity("Q1", id="Zebra"),
        entity("Q2", id="apple"),
        entity("Q3", id="Dep"),
        entity("Q4", id="Chain", claims={"P9": [ref("Q3")]}),
    )
    order = [e.id for e in emission_order(g)]
    assert order == ["Dep", "Chain", "Zebra", "apple"]


def test_emission_order_cycle_appends_remaining_sorted() -> None:
    """A specializationOf cycle is tolerated: whatever remains is appended sorted."""
    g = graph(
        entity("Q1", id="Bravo", claims={"P8": [ref("Q2")]}),
        entity("Q2", id="Alpha", claims={"P8": [ref("Q1")]}),
    )
    order = [e.id for e in emission_order(g)]
    assert order == ["Alpha", "Bravo"]


def test_emission_order_reference_target_is_not_a_dependency() -> None:
    """A dcid-only target does not block emission of the entity pointing at it."""
    g = graph(
        *bench_vocab(),
        entity("Q10", id="FinancingActivity", claims={"P4": [ref("Q4")]}),
    )
    order = [e.id for e in emission_order(g)]
    assert order == ["FinancingActivity"]


def test_node_text_statement_order_groups() -> None:
    """typeOf, name, description, alternateName, then STRUCTURAL_ORDER (only what
    is present), then remaining predicates alphabetically, minted and referenced
    alike."""
    vocab = bench_vocab()
    extra = [
        entity("P100", kind=Kind.PROPERTY, dcid="dcid:alphaProp"),
        entity("P101", kind=Kind.PROPERTY, dcid="dcid:zetaProp"),
        entity("P102", kind=Kind.PROPERTY, id="mintedProp"),
    ]
    widget = entity(
        "Q50",
        id="Widget",
        label="widget",
        description="a widget",
        aliases=["gadget"],
        claims={
            "P3": [ref("Q1")],  # typeOf -> Class
            "P4": [ref("Q4")],  # subClassOf -> Thing
            "P101": [lit("zval")],
            "P100": [lit("aval")],
            "P102": [lit("dval")],
        },
    )
    g = graph(*vocab, *extra, widget)
    text = node_text(g, widget)
    assert text == (
        "Node: dcid:Widget\n"
        "typeOf: schema:Class\n"
        'name: "widget"\n'
        'description: "a widget"\n'
        'alternateName: "gadget"\n'
        "subClassOf: schema:Thing\n"
        'alphaProp: "aval"\n'
        'mintedProp: "dval"\n'
        'zetaProp: "zval"'
    )


def test_node_text_follows_the_graph_prefix() -> None:
    """The node line and a resolved minted target read the graph's prefix; a
    minted predicate name stays bare whatever the prefix is."""
    vocab = bench_vocab()
    extra = [
        entity("P100", kind=Kind.PROPERTY, dcid="dcid:alphaProp"),
        entity("P101", kind=Kind.PROPERTY, dcid="dcid:zetaProp"),
        entity("P102", kind=Kind.PROPERTY, id="mintedProp"),
    ]
    widget = entity(
        "Q50",
        id="Widget",
        claims={
            "P3": [ref("Q1")],
            "P4": [ref("Q60")],  # subClassOf a minted target, not a reference
            "P100": [lit("aval")],
            "P101": [lit("zval")],
            "P102": [lit("dval")],
        },
    )
    g = graph(*vocab, *extra, entity("Q60", id="Gadget"), widget, prefix="example")
    assert node_text(g, widget) == (
        "Node: example:Widget\n"
        "typeOf: schema:Class\n"
        "subClassOf: example:Gadget\n"
        'alphaProp: "aval"\n'
        'mintedProp: "dval"\n'
        'zetaProp: "zval"'
    )


def test_multi_value_join_authored_order() -> None:
    """Multiple values for one predicate join with ', ' in authored order, not
    sorted."""
    vocab = bench_vocab()
    a = entity("Q20", id="Alpha")
    b = entity("Q21", id="Bravo")
    holder = entity("Q22", id="Holder", claims={"P6": [ref("Q21"), ref("Q20")]})
    g = graph(*vocab, a, b, holder)
    text = node_text(g, holder)
    assert "domainIncludes: dcid:Bravo, dcid:Alpha" in text.splitlines()


def test_quote_escaping_in_label_description_alias_and_literal() -> None:
    """Every emitted string value is escaped through model.escape."""
    vocab = bench_vocab()
    e = entity(
        "Q30",
        id="Quoted",
        label='say "hi"',
        description='a "quoted" thing',
        aliases=['also "aliased"'],
        claims={"P100": [lit('a "value"')]},
    )
    p100 = entity("P100", kind=Kind.PROPERTY, dcid="dcid:custom")
    g = graph(*vocab, p100, e)
    text = node_text(g, e)
    assert 'name: "say \\"hi\\""' in text
    assert 'description: "a \\"quoted\\" thing"' in text
    assert 'alternateName: "also \\"aliased\\""' in text
    assert 'custom: "a \\"value\\""' in text


def test_minted_property_and_constraint_property_produce_same_typeof_line() -> None:
    """schema:Property, whether injected (S2) or authored (S3), is one line."""
    vocab = bench_vocab()
    domain = entity("Q60", id="Domain")
    rng = entity("Q61", id="Range")
    minted = entity(
        "Q62",
        kind=Kind.PROPERTY,
        id="mintedProp",
        claims={"P6": [ref("Q60")], "P7": [ref("Q61")]},
    )
    constraint = entity(
        "Q63",
        id="constraintProp",
        claims={"P3": [ref("Q2")], "P6": [ref("Q60")], "P7": [ref("Q61")]},
    )
    g = graph(*vocab, domain, rng, minted, constraint)
    minted_line = node_text(g, minted).splitlines()[1]
    constraint_line = node_text(g, constraint).splitlines()[1]
    assert minted_line == constraint_line == "typeOf: schema:Property"


def test_render_value_dcid_target_passes_through_verbatim() -> None:
    """A Ref resolving to a dcid-only entity emits its dcid unchanged."""
    g = graph(*bench_vocab())
    value = render_value(g, ref("Q4"))
    assert value == "schema:Thing"


def test_render_value_defined_target_emits_prefixed_id() -> None:
    """A Ref resolving to an id-carrying entity emits dcid:<id>."""
    g = graph(entity("Q1", id="Something"))
    value = render_value(g, ref("Q1"))
    assert value == f"{PREFIX}:Something"


def test_emit_separator_and_trailing_newline() -> None:
    """The bench header, then one blank line between nodes, one trailing newline."""
    g = graph(
        entity("Q1", id="Alpha", label="alpha"), entity("Q2", id="Beta", label="beta")
    )
    text = emit(g, config=CONFIG)
    a_text = node_text(g, g.entity("Q1"))
    b_text = node_text(g, g.entity("Q2"))
    assert text == HEADER + "\n" + a_text + "\n\n" + b_text + "\n"
    assert text.count("\n\n\n") == 0


def test_emit_empty_graph_returns_bench_header_alone() -> None:
    """A graph with no id-carrying entity emits the header and no nodes."""
    g = graph(*bench_vocab())
    assert emit(g, config=CONFIG) == HEADER


def test_emit_header_names_the_bench_it_read() -> None:
    """The header carries the bench name and its browsable URL, not the API endpoint."""
    g = graph(entity("Q1", id="Alpha", label="alpha"))
    text = emit(g, config=Config(bench="prod"))
    assert text.startswith(
        "# bench: prod (https://developmentfinance.wikibase.cloud)\n"
    )
    assert "api.php" not in text


def test_predicate_merge_two_properties_same_bare_name() -> None:
    """Two properties mapping to one predicate merge into one line rather than
    one being silently lost (the I6/P2 dependency)."""
    vocab = bench_vocab()
    duplicate = entity("P106", kind=Kind.PROPERTY, dcid="dcid:domainIncludes")
    a = entity("Q70", id="TargetA")
    b = entity("Q71", id="TargetB")
    holder = entity(
        "Q72", id="Holder", claims={"P6": [ref("Q70")], "P106": [ref("Q71")]}
    )
    g = graph(*vocab, duplicate, a, b, holder)
    text = node_text(g, holder)
    assert "domainIncludes: dcid:TargetA, dcid:TargetB" in text.splitlines()


def test_emit_leaves_out_provisional_nodes_only_when_asked() -> None:
    """A provisional node emits by default, flag and all, and goes once filtered."""
    flag = entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional")
    true = entity("Q30", dcid="schema:True")
    settled = entity(
        "Q10", id="Settled", label="s", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    draft = entity(
        "Q11",
        id="Draft",
        label="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q10")], "P30": [ref("Q30")]},
    )
    g = graph(*bench_vocab(), flag, true, settled, draft)

    included = emit(g, config=CONFIG)
    assert f"Node: {PREFIX}:Draft\n" in included
    assert "isProvisional: schema:True" in included

    excluded = emit(provisional.without(g), config=CONFIG)
    assert f"Node: {PREFIX}:Draft\n" not in excluded
    assert f"Node: {PREFIX}:Settled\n" in excluded
