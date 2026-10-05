"""Tests for validate.py preflight and rules/identity.py (I1-I11, A1)."""

from dfo_ontology import validate
from dfo_ontology.model import Kind

from .graphbuild import bench_vocab, entity, graph, lit, ref


def test_bench_vocab_alone_validates_clean() -> None:
    """The live bench's own vocabulary passes with no findings at all."""
    result = validate.validate(graph(*bench_vocab()))
    assert result.ok is True
    assert result.errors == []


# --- Preflight -----------------------------------------------------------


def test_preflight_passes_on_bench_vocab() -> None:
    """No gaps, no blocked rules, over the live vocabulary."""
    pre = validate.preflight(graph(*bench_vocab()))
    assert pre.findings == ()
    assert pre.blocked == frozenset()


def test_preflight_p1_missing_id_property() -> None:
    """A missing id property is one P1 finding, and blocks I1 among others."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    pre = validate.preflight(graph(*vocab))
    assert [f.rule for f in pre.findings] == ["P1"]
    assert pre.blocked == validate.BLOCKED_BY_GAP["id property"]


def test_preflight_p1_wrong_kind() -> None:
    """An id property that is an item, not a property, is P1."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    vocab.append(entity("P1", kind=Kind.ITEM))
    pre = validate.preflight(graph(*vocab))
    assert [f.rule for f in pre.findings] == ["P1"]
    assert pre.blocked == validate.BLOCKED_BY_GAP["id property"]


def test_preflight_p2_ambiguous_structural_predicate() -> None:
    """Two properties claiming typeOf is one P2 finding naming both, blocking S7."""
    dup = entity("P99", kind=Kind.PROPERTY, dcid="dcid:typeOf")
    pre = validate.preflight(graph(*bench_vocab(), dup))
    p2 = [f for f in pre.findings if f.rule == "P2"]
    assert len(p2) == 1
    assert p2[0].value == "typeOf"
    assert "P3" in p2[0].message
    assert "P99" in p2[0].message
    assert "S7" in pre.blocked


def test_preflight_p3_missing_well_known_items() -> None:
    """Each of the four well-known items missing produces its own P3 finding."""
    for qid, name in [
        ("Q1", "Class"),
        ("Q2", "Property"),
        ("Q3", "Enumeration"),
        ("Q4", "Thing"),
    ]:
        vocab = [e for e in bench_vocab() if e.qid != qid]
        pre = validate.preflight(graph(*vocab))
        assert any(f.rule == "P3" and f.value == name for f in pre.findings)
        assert pre.blocked == validate.BLOCKED_BY_GAP[f"{name} item"]


def test_preflight_p3_ambiguous_well_known_item() -> None:
    """Two items claiming Class is P3, naming both."""
    dup = entity("Q99", dcid="schema:Class")
    pre = validate.preflight(graph(*bench_vocab(), dup))
    p3 = [f for f in pre.findings if f.rule == "P3" and f.value == "Class"]
    assert len(p3) == 1
    assert "Q1" in p3[0].message
    assert "Q99" in p3[0].message


def test_missing_id_property_blocks_identity_layer_with_one_finding() -> None:
    """A missing id property produces one finding, not one per entity."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    extra = [entity("Q10", id="A"), entity("Q11", id="B")]
    result = validate.validate(graph(*vocab, *extra))
    assert [f.rule for f in result.errors] == ["P1"]
    assert result.not_run == validate.BLOCKED_BY_GAP["id property"]


def test_missing_id_property_blocks_the_value_rules_too() -> None:
    """I8 and I11 walk id-carrying entities, so a missing id property blocks them.

    Without the gap they would pass vacuously over a bench where they inspected
    no value at all, and the report would not say so.
    """
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    result = validate.validate(graph(*vocab, entity("Q10", id="A", label="A")))
    assert {"I8", "I11"} <= result.not_run


def test_class_item_gap_does_not_error_on_domain_and_range() -> None:
    """P3 owns a Class-item gap; G3 and G4 stay quiet instead of firing per statement.

    Both gaps are covered: the item is present but no longer claims the Class
    dcid, and two items claim it. Either way a target typed through the wrong
    claimant would otherwise read as "not typed Class".
    """
    a_class = entity(
        "Q10", id="SomeClass", label="A", description="d", claims={"P3": [ref("Q1")]}
    )
    property_ = entity(
        "Q12",
        id="someProperty",
        label="P",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q10")], "P7": [ref("Q10")]},
    )

    typo = [e for e in bench_vocab() if e.qid != "Q1"]
    typo.append(entity("Q1", dcid="schema:NotClass", claims={"P3": [ref("Q1")]}))
    duplicate = [*bench_vocab(), entity("Q99", dcid="dcid:Class")]

    for vocab in (typo, duplicate):
        result = validate.validate(graph(*vocab, a_class, property_))
        assert not [f for f in result.errors if f.rule in ("G3", "G4")]
        assert {"G3", "G4"} <= result.not_run
        assert any(f.rule == "P3" for f in result.errors)


def test_missing_dcid_property_blocks_i3() -> None:
    """I3 is blocked, not vacuously passed, when the dcid property is absent."""
    vocab = [e for e in bench_vocab() if e.qid != "P2"]
    result = validate.validate(graph(*vocab))
    assert "I3" in result.not_run
    assert not any(f.rule == "I3" for f in result.errors)


def test_missing_dcid_property_does_not_block_i4() -> None:
    """A malformed id still reports I4 when only the dcid property is missing.

    I1 sits in both bookkeeping blocked rows, so a guard coarser than
    per-rule would wrongly skip every other identity rule here too.
    """
    vocab = [e for e in bench_vocab() if e.qid != "P2"]
    e = entity("Q10", id="basic-health", label="A", description="d")
    result = validate.validate(graph(*vocab, e))
    assert "I4" not in result.not_run
    assert any(f.rule == "I4" and f.entity is e for f in result.errors)


# --- I1: exactly one of id/dcid -------------------------------------------


def test_i1_single_identifier_passes() -> None:
    """An entity carrying only an id has no I1 finding."""
    e = entity("Q10", id="A", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I1" for f in result.errors)


def test_i1_neither_is_an_error() -> None:
    """Carrying neither id nor dcid is I1."""
    e = entity("Q10", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert [f.rule for f in result.errors if f.entity is e] == ["I1"]


def test_i1_both_is_an_error() -> None:
    """Carrying both id and dcid is I1."""
    e = entity("Q10", id="A", dcid="schema:A", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert [f.rule for f in result.errors if f.entity is e] == ["I1"]


def test_i1_exempts_the_bookkeeping_properties() -> None:
    """P1 and P2 carry neither, and that is not an I1 finding."""
    result = validate.validate(graph(*bench_vocab()))
    assert not any(f.rule == "I1" for f in result.errors)


# --- I2: at most one statement of each ------------------------------------


def test_i2_single_statement_passes() -> None:
    """A single id statement has no I2 finding."""
    e = entity("Q10", id="A", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I2" for f in result.errors)


def test_i2_two_id_statements_is_an_error() -> None:
    """Two id statements on one entity is I2."""
    e = entity("Q10", id="A", label="A", description="d", claims={"P1": [lit("B")]})
    result = validate.validate(graph(*bench_vocab(), e))
    i2 = [f for f in result.errors if f.rule == "I2" and f.entity is e]
    assert len(i2) == 1
    assert i2[0].predicate == "id"


def test_i2_two_dcid_statements_is_an_error() -> None:
    """Two dcid statements on one entity is I2."""
    e = entity("Q10", dcid="schema:A", claims={"P2": [lit("schema:B")]})
    result = validate.validate(graph(*bench_vocab(), e))
    i2 = [f for f in result.errors if f.rule == "I2" and f.entity is e]
    assert len(i2) == 1
    assert i2[0].predicate == "dcid"


# --- I3: bookkeeping properties carry neither -----------------------------


def test_i3_passes_on_bench_vocab() -> None:
    """P1 and P2 carrying neither id nor dcid is the passing case."""
    result = validate.validate(graph(*bench_vocab()))
    assert not any(f.rule == "I3" for f in result.errors)


def test_i3_bookkeeping_property_carrying_an_id_is_an_error() -> None:
    """The id property itself carrying an id is I3."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    vocab.append(entity("P1", kind=Kind.PROPERTY, id="idProperty", label="id"))
    result = validate.validate(graph(*vocab))
    assert any(f.rule == "I3" for f in result.errors)


# --- I4: id syntax ---------------------------------------------------------


def test_i4_valid_id_passes() -> None:
    """A letter-and-digit id has no I4 finding."""
    e = entity("Q10", id="BasicHealth", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I4" for f in result.errors)


def test_i4_bad_id_format_is_an_error() -> None:
    """A hyphenated id is I4."""
    e = entity("Q10", id="basic-health", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.rule == "I4" and f.entity is e for f in result.errors)


# --- I5: id uniqueness -----------------------------------------------------


def test_i5_unique_id_passes() -> None:
    """A non-duplicated id has no I5 finding."""
    e = entity("Q10", id="Foo", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I5" for f in result.errors)


def test_i5_duplicate_id_names_every_claimant() -> None:
    """A duplicate id is one cross-entity finding naming both claimants."""
    a = entity("Q10", id="Foo", label="A", description="d")
    b = entity("Q11", id="Foo", label="B", description="d")
    result = validate.validate(graph(*bench_vocab(), a, b))
    i5 = [f for f in result.errors if f.rule == "I5"]
    assert len(i5) == 1
    assert i5[0].entity is None
    assert "Q10" in i5[0].message
    assert "Q11" in i5[0].message


# --- I6: dcid prefix and uniqueness ----------------------------------------


def test_i6_valid_dcid_passes() -> None:
    """A prefixed, non-duplicated dcid has no I6 finding."""
    e = entity("Q10", dcid="schema:Foo")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I6" for f in result.errors)


def test_i6_unprefixed_dcid_is_an_error() -> None:
    """A dcid with no colon is I6."""
    e = entity("Q10", dcid="Organization")
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.rule == "I6" and f.entity is e for f in result.errors)


def test_i6_duplicate_dcid_is_a_cross_entity_error() -> None:
    """A duplicate dcid is one cross-entity finding naming both claimants."""
    a = entity("Q10", dcid="schema:Foo")
    b = entity("Q11", dcid="schema:Foo")
    result = validate.validate(graph(*bench_vocab(), a, b))
    i6 = [f for f in result.errors if f.rule == "I6" and f.entity is None]
    assert len(i6) == 1
    assert "Q10" in i6[0].message
    assert "Q11" in i6[0].message


# --- I7: dcid:<id> length ----------------------------------------------------


def test_i7_short_id_passes() -> None:
    """A short id has no I7 finding."""
    e = entity("Q10", id="Foo", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I7" for f in result.errors)


def test_i7_id_over_256_characters_is_an_error() -> None:
    """A 260-character id pushes dcid:<id> past the 256-character limit."""
    long_id = "A" + "a" * 259
    e = entity("Q10", id=long_id, label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.rule == "I7" and f.entity is e for f in result.errors)


# --- I8: emitted value length -----------------------------------------------


def test_i8_short_values_pass() -> None:
    """Short label, description, and aliases have no I8 finding."""
    e = entity("Q10", id="Foo", label="A", description="d", aliases=["b"])
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I8" for f in result.errors)


def test_i8_label_over_65535_characters_is_an_error() -> None:
    """A 65,536-character label is I8, naming the name predicate."""
    e = entity("Q10", id="Foo", label="a" * 65536, description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    i8 = [f for f in result.errors if f.rule == "I8" and f.entity is e]
    assert any(f.predicate == "name" for f in i8)


def test_i8_description_over_65535_characters_is_an_error() -> None:
    """A 65,536-character description is I8, naming the description predicate."""
    e = entity("Q10", id="Foo", label="A", description="a" * 65536)
    result = validate.validate(graph(*bench_vocab(), e))
    i8 = [f for f in result.errors if f.rule == "I8" and f.entity is e]
    assert any(f.predicate == "description" for f in i8)


def test_i8_alias_over_65535_characters_is_an_error() -> None:
    """A 65,536-character alias is I8, naming alternateName."""
    e = entity("Q10", id="Foo", label="A", description="d", aliases=["a" * 65536])
    result = validate.validate(graph(*bench_vocab(), e))
    i8 = [f for f in result.errors if f.rule == "I8" and f.entity is e]
    assert any(f.predicate == "alternateName" for f in i8)


def test_i8_literal_claim_over_65535_characters_is_an_error() -> None:
    """A 65,536-character literal claim value is I8, naming its predicate."""
    e = entity(
        "Q10",
        id="Foo",
        label="A",
        description="d",
        claims={"P6": [lit("a" * 65536)]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    i8 = [f for f in result.errors if f.rule == "I8" and f.entity is e]
    assert any(f.predicate == "domainIncludes" for f in i8)


# --- I11: no emitted value may contain a backslash --------------------------


def test_i11_values_with_no_backslash_pass() -> None:
    """Label, description, and aliases with no backslash have no I11 finding."""
    e = entity("Q10", id="Foo", label="A", description="d", aliases=["b"])
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I11" for f in result.errors)


def test_i11_backslash_in_label_is_an_error() -> None:
    """A backslash in the label is I11, naming the name predicate."""
    e = entity("Q10", id="Foo", label=r"Foo\Bar", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    i11 = [f for f in result.errors if f.rule == "I11" and f.entity is e]
    assert any(f.predicate == "name" for f in i11)


def test_i11_backslash_in_description_is_an_error() -> None:
    """A backslash in the description is I11, naming the description predicate."""
    e = entity("Q10", id="Foo", label="A", description=r"has a \ in it")
    result = validate.validate(graph(*bench_vocab(), e))
    i11 = [f for f in result.errors if f.rule == "I11" and f.entity is e]
    assert any(f.predicate == "description" for f in i11)


def test_i11_backslash_in_alias_is_an_error() -> None:
    """A backslash in an alias is I11, naming alternateName."""
    e = entity("Q10", id="Foo", label="A", description="d", aliases=[r"al\ias"])
    result = validate.validate(graph(*bench_vocab(), e))
    i11 = [f for f in result.errors if f.rule == "I11" and f.entity is e]
    assert any(f.predicate == "alternateName" for f in i11)


def test_i11_backslash_in_literal_claim_is_an_error() -> None:
    """A backslash in a literal claim value is I11, naming its predicate."""
    e = entity(
        "Q10",
        id="Foo",
        label="A",
        description="d",
        claims={"P6": [lit(r"has a \ in it")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    i11 = [f for f in result.errors if f.rule == "I11" and f.entity is e]
    assert any(f.predicate == "domainIncludes" for f in i11)


# --- I9: shape-aware casing --------------------------------------------------


def test_i9_property_id_must_be_lowercase() -> None:
    """A minted property's id starts lowercase; uppercase is I9."""
    good = entity(
        "P9", kind=Kind.PROPERTY, id="financingPurpose", label="A", description="d"
    )
    bad = entity(
        "P9", kind=Kind.PROPERTY, id="FinancingPurpose", label="A", description="d"
    )
    assert not any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), good)).errors
    )
    assert any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), bad)).errors
    )


def test_i9_constraint_property_id_must_be_lowercase() -> None:
    """A constraint property is a property too: camelCase, not PascalCase."""
    good = entity(
        "Q10",
        id="financingPurpose",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")]},
    )
    bad = entity(
        "Q10",
        id="FinancingPurpose",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")]},
    )
    assert not any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), good)).errors
    )
    assert any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), bad)).errors
    )


def test_i9_class_id_must_be_uppercase() -> None:
    """A class's id starts uppercase; lowercase is I9."""
    good = entity(
        "Q10",
        id="SomeClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")]},
    )
    bad = entity(
        "Q10",
        id="someClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")]},
    )
    assert not any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), good)).errors
    )
    assert any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), bad)).errors
    )


def test_i9_value_list_id_must_end_in_enum() -> None:
    """A value list's id ends in Enum; without it that is I9."""
    good = entity(
        "Q10",
        id="FinancingPurposeEnum",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    bad = entity(
        "Q10",
        id="FinancingPurpose",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    assert not any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), good)).errors
    )
    assert any(
        f.rule == "I9" for f in validate.validate(graph(*bench_vocab(), bad)).errors
    )


def test_i9_blind_reach_skips_the_enum_clause() -> None:
    """A class whose subClassOf chain dead-ends at a reference skips the Enum check."""
    reference = entity("Q12", dcid="schema:Organization")
    e = entity(
        "Q10",
        id="SomeClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q12")]},
    )
    result = validate.validate(graph(*bench_vocab(), e, reference))
    assert not any(f.rule == "I9" for f in result.errors)


def test_i9_undetermined_shape_skips_entirely() -> None:
    """An entity whose shape cannot be determined skips I9 altogether."""
    e = entity("Q10", id="lowercase", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I9" for f in result.errors)


# --- I10: English label -----------------------------------------------------


def test_i10_label_present_passes() -> None:
    """An id-carrying entity with a label has no I10 finding."""
    e = entity("Q10", id="Foo", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule == "I10" for f in result.errors)


def test_i10_missing_label_is_an_error() -> None:
    """An id-carrying entity with no label is I10."""
    e = entity("Q10", id="Foo", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.rule == "I10" and f.entity is e for f in result.errors)


# --- A1: missing description is advisory ------------------------------------


def test_a1_missing_description_is_advisory_not_error() -> None:
    """A missing description lands in advisories and leaves result.ok True."""
    e = entity("Q10", id="Foo", label="A", claims={"P3": [ref("Q4")]})
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.rule == "A1" and f.entity is e for f in result.advisories)
    assert not any(f.rule == "A1" for f in result.errors)
    assert result.ok is True


def test_i4_admits_a_namespace_segment() -> None:
    """`country/PacificIslandsUS` is a legal id: a local name under a namespace."""
    e = entity(
        "Q10",
        id="country/PacificIslandsUS",
        label="Pacific Islands (US)",
        description="d",
        claims={"P3": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.rule in {"I4", "I9"} for f in result.errors)


def test_i4_still_rejects_a_stray_slash() -> None:
    """A namespace segment is one lowercase segment, not any slash anywhere."""
    for bad in ("Country/Foo", "country//Foo", "a/b/Foo", "/Foo"):
        e = entity(
            "Q10", id=bad, label="A", description="d", claims={"P3": [ref("Q4")]}
        )
        result = validate.validate(graph(*bench_vocab(), e))
        assert any(f.rule == "I4" and f.entity is e for f in result.errors), bad


def test_i9_judges_the_local_name_not_the_namespace() -> None:
    """A lowercase namespace does not make a node look like a property."""
    e = entity(
        "Q10",
        id="country/pacificIslands",
        label="A",
        description="d",
        claims={"P3": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert [f.message for f in result.errors if f.rule == "I9"] == [
        "must start with an uppercase letter"
    ]
