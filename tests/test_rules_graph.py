"""Tests for rules/graph.py (G1-G11, A2)."""

from dfo_ontology import validate
from dfo_ontology.model import Entity, Finding, Kind

from .graphbuild import (
    advisories,
    bench_vocab,
    entity,
    errors,
    graph,
    lit,
    ref,
    skips,
)

# --- G1: every referenced entity exists ---------------------------------------


def test_g1_resolvable_reference_passes() -> None:
    """A domainIncludes target that exists has no G1 finding."""
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), prop))
    assert errors(result, "G1") == []


def test_g1_dangling_reference_is_an_error() -> None:
    """A domainIncludes target that does not exist is G1, naming the raw qid."""
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q999")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), prop))
    g1 = errors(result, "G1")
    assert len(g1) == 1
    assert g1[0].predicate == "domainIncludes"
    assert g1[0].value == "Q999"


# --- G2: typeOf targets Class itself, or an item typed Class -------------------


def test_g2_typeof_target_typed_class_passes() -> None:
    """A typeOf target that is itself typed Class, not Class directly, passes."""
    class_a = entity(
        "Q20",
        id="ClassA",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    individual_b = entity(
        "Q21",
        id="IndividualB",
        label="B",
        description="d",
        claims={"P3": [ref("Q20")]},
    )
    result = validate.validate(graph(*bench_vocab(), class_a, individual_b))
    assert errors(result, "G2") == []


def test_g2_typeof_target_not_typed_class_is_an_error() -> None:
    """A typeOf target whose own typeOf is not Class is G2."""
    target_typed_thing = entity(
        "Q20",
        id="TargetTypedThing",
        label="T",
        description="d",
        claims={"P3": [ref("Q4")]},
    )
    e = entity(
        "Q21",
        id="UsesBadTarget",
        label="A",
        description="d",
        claims={"P3": [ref("Q20")]},
    )
    result = validate.validate(graph(*bench_vocab(), target_typed_thing, e))
    g2 = errors(result, "G2")
    assert any(f.predicate == "typeOf" and f.entity is e for f in g2)


# --- G3: domainIncludes targets an item typed Class -----------------------------


def test_g3_domain_typed_class_passes() -> None:
    """A domainIncludes target typed Class has no G3 finding."""
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), prop))
    assert errors(result, "G3") == []


def test_g3_domain_not_typed_class_is_an_error() -> None:
    """A domainIncludes target not typed Class is G3."""
    not_a_class = entity(
        "Q30", id="NotAClass", label="N", description="d", claims={"P3": [ref("Q4")]}
    )
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q30")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), not_a_class, prop))
    g3 = errors(result, "G3")
    assert any(f.predicate == "domainIncludes" for f in g3)


def test_g3_blind_domain_target_is_a_skip() -> None:
    """A domainIncludes target with no local typing is a skip, not an error."""
    blind_ref = entity("Q31", dcid="schema:SomeBlindThing")
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q31")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), blind_ref, prop))
    assert errors(result, "G3") == []
    skip_findings = skips(result, "G3")
    assert len(skip_findings) == 1
    assert skip_findings[0].predicate == "domainIncludes"


# --- G4: rangeIncludes targets an item typed Class ------------------------------


def test_g4_range_typed_class_passes() -> None:
    """A rangeIncludes target typed Class has no G4 finding."""
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), prop))
    assert errors(result, "G4") == []


def test_g4_range_not_typed_class_is_an_error() -> None:
    """A rangeIncludes target not typed Class is G4."""
    not_a_class = entity(
        "Q30", id="NotAClass", label="N", description="d", claims={"P3": [ref("Q4")]}
    )
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q30")]},
    )
    result = validate.validate(graph(*bench_vocab(), not_a_class, prop))
    g4 = errors(result, "G4")
    assert any(f.predicate == "rangeIncludes" for f in g4)


def test_g4_blind_range_target_is_a_skip() -> None:
    """A rangeIncludes target with no local typing is a skip, not an error.

    This is what covers primitives: a bare `schema:Text`-style reference
    produces a skip, never an error.
    """
    blind_ref = entity("Q32", dcid="schema:Text")
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q32")]},
    )
    result = validate.validate(graph(*bench_vocab(), blind_ref, prop))
    assert errors(result, "G4") == []
    skip_findings = skips(result, "G4")
    assert len(skip_findings) == 1
    assert skip_findings[0].predicate == "rangeIncludes"


def test_g3_domain_typed_datatype_is_an_error() -> None:
    """A domain may not be a data type: what a property describes is an entity."""
    datatype = entity("Q33", dcid="schema:DataType", claims={"P3": [ref("Q1")]})
    text = entity("Q34", dcid="schema:Text", claims={"P3": [ref("Q33")]})
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q34")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), datatype, text, prop))
    g3 = errors(result, "G3")
    assert [f.message for f in g3] == ["not typed Class"]


def test_g4_range_typed_datatype_passes() -> None:
    """A range may be a data type — Data Commons types Text as DataType."""
    datatype = entity("Q33", dcid="schema:DataType", claims={"P3": [ref("Q1")]})
    text = entity("Q34", dcid="schema:Text", claims={"P3": [ref("Q33")]})
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q34")]},
    )
    result = validate.validate(graph(*bench_vocab(), datatype, text, prop))
    assert errors(result, "G4") == []
    assert skips(result, "G4") == []


def test_g4_range_typed_neither_names_both_admitted_typings() -> None:
    """The G4 message says what a range may be, not just that it isn't a Class."""
    not_a_class = entity(
        "Q30", id="NotAClass", label="N", description="d", claims={"P3": [ref("Q4")]}
    )
    prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="constraintProp",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q30")]},
    )
    result = validate.validate(graph(*bench_vocab(), not_a_class, prop))
    assert [f.message for f in errors(result, "G4")] == ["not typed Class or DataType"]


# --- G5: an id-carrying class reaches exactly one of Thing or Enumeration ------


def test_g5_reaches_thing_passes() -> None:
    """A class whose chain reaches Thing has no G5 finding."""
    reaches_thing = entity(
        "Q40",
        id="ReachesThing",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), reaches_thing))
    assert errors(result, "G5") == []
    assert skips(result, "G5") == []


def test_g5_reaches_both_is_an_error() -> None:
    """A class whose chain reaches both Thing and Enumeration is G5."""
    reaches_thing = entity(
        "Q40", id="ReachesThing", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    reaches_enum = entity(
        "Q41", id="ReachesEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    both_roots = entity(
        "Q42",
        id="BothRoots",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q40"), ref("Q41")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), reaches_thing, reaches_enum, both_roots)
    )
    g5 = errors(result, "G5")
    assert any(f.entity is both_roots and "both" in f.message for f in g5)


def test_g5_reaches_neither_is_an_error() -> None:
    """A class with no subClassOf statement reaches neither, which is G5."""
    dead_end = entity(
        "Q50", id="DeadEndClass", label="A", description="d", claims={"P3": [ref("Q1")]}
    )
    result = validate.validate(graph(*bench_vocab(), dead_end))
    g5 = errors(result, "G5")
    assert any(f.entity is dead_end and "neither" in f.message for f in g5)


def test_g5_blind_chain_is_a_skip() -> None:
    """A subClassOf chain dead-ending at a blind reference is a skip, not an error."""
    blind_ref = entity("Q51", dcid="schema:SomeBlindThing")
    blind_chain = entity(
        "Q52",
        id="BlindChainClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q51")]},
    )
    result = validate.validate(graph(*bench_vocab(), blind_ref, blind_chain))
    assert not any(f.entity is blind_chain for f in errors(result, "G5"))
    assert any(f.entity is blind_chain for f in skips(result, "G5"))


def test_g5_does_not_fire_on_the_live_bench_reference_items() -> None:
    """The reference items carry no id, so G5 never sees them."""
    result = validate.validate(graph(*bench_vocab()))
    assert errors(result, "G5") == []
    assert skips(result, "G5") == []


# --- G6: subPropertyOf connects two properties ---------------------------------


def test_g6_subproperty_target_is_a_property_passes() -> None:
    """A subPropertyOf target that is a property has no G6 finding."""
    generic_prop = entity(
        "P20",
        kind=Kind.PROPERTY,
        id="genericProp",
        label="A",
        description="d",
        claims={"P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    e = entity(
        "Q60",
        id="GoodSubProperty",
        label="A",
        description="d",
        claims={
            "P3": [ref("Q2")],
            "P6": [ref("Q4")],
            "P7": [ref("Q4")],
            "P5": [ref("P20")],
        },
    )
    result = validate.validate(graph(*bench_vocab(), generic_prop, e))
    assert errors(result, "G6") == []


def test_g6_subproperty_target_not_a_property_is_an_error() -> None:
    """A subPropertyOf target that is an individual, not a property, is G6."""
    not_a_property = entity(
        "Q61", id="NotAProperty", label="N", description="d", claims={"P3": [ref("Q4")]}
    )
    e = entity(
        "Q62",
        id="BadSubProperty",
        label="A",
        description="d",
        claims={
            "P3": [ref("Q2")],
            "P6": [ref("Q4")],
            "P7": [ref("Q4")],
            "P5": [ref("Q61")],
        },
    )
    result = validate.validate(graph(*bench_vocab(), not_a_property, e))
    g6 = errors(result, "G6")
    assert any(f.value == "dcid:NotAProperty" for f in g6)


# --- G7: specializationOf targets a value in the same list ----------------------


def test_g7_same_list_passes() -> None:
    """specializationOf targeting a value in the same list has no G7 finding."""
    color_enum = entity(
        "Q70", id="ColorEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    red = entity(
        "Q71", id="Red", label="Red", description="d", claims={"P3": [ref("Q70")]}
    )
    blue = entity(
        "Q72",
        id="Blue",
        label="Blue",
        description="d",
        claims={"P3": [ref("Q70")], "P8": [ref("Q71")]},
    )
    result = validate.validate(graph(*bench_vocab(), color_enum, red, blue))
    assert errors(result, "G7") == []


def test_g7_different_list_is_an_error() -> None:
    """specializationOf targeting a value in a different list is G7."""
    color_enum = entity(
        "Q70", id="ColorEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    shape_enum = entity(
        "Q73", id="ShapeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    circle = entity(
        "Q74", id="Circle", label="Circle", description="d", claims={"P3": [ref("Q73")]}
    )
    green = entity(
        "Q75",
        id="Green",
        label="Green",
        description="d",
        claims={"P3": [ref("Q70")], "P8": [ref("Q74")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), color_enum, shape_enum, circle, green)
    )
    g7 = errors(result, "G7")
    assert len(g7) == 1
    assert g7[0].predicate == "specializationOf"
    assert g7[0].value == "dcid:Circle"
    assert g7[0].message == "not a value in the same list"


# --- G8: no cycles in subClassOf or subPropertyOf -------------------------------


def test_g8_no_cycle_passes() -> None:
    """An acyclic subClassOf chain has no G8 finding."""
    a_class = entity(
        "Q80",
        id="PlainClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), a_class))
    assert errors(result, "G8") == []


def test_g8_subclassof_cycle_is_one_cross_entity_finding() -> None:
    """A subClassOf cycle is one cross-entity G8 finding naming both members."""
    a = entity("Q80", id="CycleClassA", claims={"P3": [ref("Q1")], "P4": [ref("Q81")]})
    b = entity("Q81", id="CycleClassB", claims={"P3": [ref("Q1")], "P4": [ref("Q80")]})
    result = validate.validate(graph(*bench_vocab(), a, b))
    g8 = [f for f in errors(result, "G8") if f.value == "subClassOf cycle"]
    assert len(g8) == 1
    assert g8[0].entity is None
    assert "Q80" in g8[0].message
    assert "Q81" in g8[0].message


def test_g8_subpropertyof_cycle_is_one_cross_entity_finding() -> None:
    """A subPropertyOf cycle is one cross-entity G8 finding, reported separately."""
    prop_a = entity(
        "P30",
        kind=Kind.PROPERTY,
        id="propA",
        claims={"P6": [ref("Q4")], "P7": [ref("Q4")], "P5": [ref("P31")]},
    )
    prop_b = entity(
        "P31",
        kind=Kind.PROPERTY,
        id="propB",
        claims={"P6": [ref("Q4")], "P7": [ref("Q4")], "P5": [ref("P30")]},
    )
    result = validate.validate(graph(*bench_vocab(), prop_a, prop_b))
    g8 = [f for f in errors(result, "G8") if f.value == "subPropertyOf cycle"]
    assert len(g8) == 1
    assert g8[0].entity is None
    assert "P30" in g8[0].message
    assert "P31" in g8[0].message


def test_g8_specializationof_cycle_is_one_cross_entity_finding() -> None:
    """Two values each specialising the other is a G8 cycle, and blocks emission.

    Both ends satisfy G7 — they are values in the same list — so nothing else in
    the rulebook catches the contradiction.
    """
    value_list = entity(
        "Q80",
        id="PurposeEnum",
        label="purpose",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    alpha = entity(
        "Q81",
        id="PurposeAlpha",
        label="alpha",
        description="d",
        claims={"P3": [ref("Q80")], "P8": [ref("Q82")]},
    )
    beta = entity(
        "Q82",
        id="PurposeBeta",
        label="beta",
        description="d",
        claims={"P3": [ref("Q80")], "P8": [ref("Q81")]},
    )
    result = validate.validate(graph(*bench_vocab(), value_list, alpha, beta))
    g8 = [f for f in errors(result, "G8") if f.value == "specializationOf cycle"]
    assert len(g8) == 1
    assert g8[0].entity is None
    assert "Q81" in g8[0].message
    assert "Q82" in g8[0].message
    assert errors(result, "G7") == []
    assert result.ok is False


# --- G9: classificationCode only on values, unique within its list -------------


def test_g9_no_ops_when_classification_code_is_absent() -> None:
    """No G9 finding fires while classificationCode is not minted on the bench."""
    assert graph(*bench_vocab()).entity_by_id("classificationCode") is None
    result = validate.validate(graph(*bench_vocab()))
    assert errors(result, "G9") == []


def test_g9_unique_codes_within_a_list_pass() -> None:
    """Distinct classificationCode values within one list have no G9 finding."""
    code_prop = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
    fruit_enum = entity(
        "Q90", id="FruitEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    apple = entity(
        "Q91",
        id="Apple",
        label="Apple",
        description="d",
        claims={"P3": [ref("Q90")], "P40": [lit("APL")]},
    )
    banana = entity(
        "Q92",
        id="Banana",
        label="Banana",
        description="d",
        claims={"P3": [ref("Q90")], "P40": [lit("BAN")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), code_prop, fruit_enum, apple, banana)
    )
    assert errors(result, "G9") == []


def test_g9_ignores_daccode_duplicates() -> None:
    """Two individuals sharing a dacCode have no G9 finding — the rule is
    pinned to classificationCode; a register code may repeat."""
    code_prop = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
    dac_prop = entity("P41", kind=Kind.PROPERTY, id="dacCode")
    a_class = entity(
        "Q90", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    one = entity(
        "Q91",
        id="OneOrg",
        label="one",
        description="d",
        claims={"P3": [ref("Q90")], "P41": [lit("913")]},
    )
    two = entity(
        "Q92",
        id="TwoOrg",
        label="two",
        description="d",
        claims={"P3": [ref("Q90")], "P41": [lit("913")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), code_prop, dac_prop, a_class, one, two)
    )
    assert errors(result, "G9") == []


def test_g9_only_allowed_on_a_value_is_an_error() -> None:
    """classificationCode stated on a non-value entity is G9."""
    code_prop = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
    not_a_value = entity(
        "Q93",
        id="NotAValue",
        label="N",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")], "P40": [lit("XYZ")]},
    )
    result = validate.validate(graph(*bench_vocab(), code_prop, not_a_value))
    g9 = errors(result, "G9")
    assert any(
        f.entity is not_a_value and "only allowed on a value" in f.message for f in g9
    )


def test_g9_duplicate_code_within_a_list_is_a_cross_entity_error() -> None:
    """Two values in one list sharing a classificationCode is G9, naming both."""
    code_prop = entity("P40", kind=Kind.PROPERTY, id="classificationCode")
    fruit_enum = entity(
        "Q90", id="FruitEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    apple = entity(
        "Q91",
        id="Apple",
        label="Apple",
        description="d",
        claims={"P3": [ref("Q90")], "P40": [lit("APL")]},
    )
    cherry = entity(
        "Q94",
        id="Cherry",
        label="Cherry",
        description="d",
        claims={"P3": [ref("Q90")], "P40": [lit("APL")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), code_prop, fruit_enum, apple, cherry)
    )
    g9 = [f for f in errors(result, "G9") if f.entity is None]
    assert len(g9) == 1
    assert "Q91" in g9[0].message
    assert "Q94" in g9[0].message


# --- G10: nationalCurrencyOf only on a current currency ----------------------------


def _currency_vocab() -> list[Entity]:
    """currencyStatus (P13) and nationalCurrencyOf (P19), the bench's own qids; a
    CurrencyUnit class (Q120); a CurrencyStatusEnum list (Q121) with its Current
    (Q122) and Withdrawn (Q123) values; and two Country individuals, France (Q124)
    and Germany (Q125)."""
    return [
        entity("P13", kind=Kind.PROPERTY, id="currencyStatus"),
        entity("P19", kind=Kind.PROPERTY, id="nationalCurrencyOf"),
        entity(
            "Q120",
            id="CurrencyUnit",
            label="c",
            description="d",
            claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
        ),
        entity(
            "Q121",
            id="CurrencyStatusEnum",
            label="s",
            description="d",
            claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
        ),
        entity(
            "Q122",
            id="CurrencyStatusCurrent",
            label="current",
            description="d",
            claims={"P3": [ref("Q121")]},
        ),
        entity(
            "Q123",
            id="CurrencyStatusWithdrawn",
            label="withdrawn",
            description="d",
            claims={"P3": [ref("Q121")]},
        ),
        entity(
            "Q124",
            id="France",
            label="France",
            description="d",
            claims={"P3": [ref("Q120")]},
        ),
        entity(
            "Q125",
            id="Germany",
            label="Germany",
            description="d",
            claims={"P3": [ref("Q120")]},
        ),
    ]


def _currency(
    qid: str, *, id: str, status: str | None, places: tuple[str, ...] = ("Q124",)
) -> Entity:
    """A CurrencyUnit that is the national currency of these places, France by
    default, carrying this currencyStatus target, if any."""
    claims = {"P3": [ref("Q120")], "P19": [ref(place) for place in places]}
    if status is not None:
        claims["P13"] = [ref(status)]
    return entity(qid, id=id, label=id, description="d", claims=claims)


def test_g10_current_currency_stating_national_currency_of_passes() -> None:
    """A currency whose status is CurrencyStatusCurrent may state nationalCurrencyOf."""
    eur = _currency("Q130", id="CurrencyEUR", status="Q122")
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), eur))
    assert errors(result, "G10") == []
    assert errors(result, "S6") == []


def test_g10_withdrawn_currency_stating_national_currency_of_is_an_error() -> None:
    """A withdrawn currency stating nationalCurrencyOf is G10."""
    frf = _currency("Q130", id="CurrencyFRF", status="Q123")
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), frf))
    g10 = errors(result, "G10")
    assert [(f.entity, f.predicate) for f in g10] == [(frf, "nationalCurrencyOf")]
    assert "CurrencyStatusCurrent" in g10[0].message


def test_g10_entity_with_no_status_stating_national_currency_of_is_an_error() -> None:
    """An entity stating nationalCurrencyOf with no currencyStatus at all is G10."""
    unstated = _currency("Q130", id="CurrencyXXX", status=None)
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), unstated))
    assert [f.entity for f in errors(result, "G10")] == [unstated]


def test_g10_dangling_status_reads_as_not_current() -> None:
    """A currencyStatus pointing at nothing is G1, and the currency is G10."""
    dangling = _currency("Q130", id="CurrencyXXX", status="Q999")
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), dangling))
    assert [f.entity for f in errors(result, "G10")] == [dangling]
    assert any(f.entity is dangling for f in errors(result, "G1"))


def test_g10_no_ops_while_national_currency_of_is_unminted() -> None:
    """With nationalCurrencyOf unminted, P19 is an unknown property and G10 is silent."""
    vocab = [e for e in _currency_vocab() if e.qid != "P19"]
    frf = _currency("Q130", id="CurrencyFRF", status="Q123")
    result = validate.validate(graph(*bench_vocab(), *vocab, frf))
    assert errors(result, "G10") == []


def test_g10_not_run_without_the_id_property() -> None:
    """A missing id property blocks G10, since every name it matches is an id."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    result = validate.validate(graph(*vocab, *_currency_vocab()))
    assert "G10" in result.not_run


# --- G11: one national currency per place ---------------------------------------


def test_g11_currency_shared_by_two_places_passes() -> None:
    """One currency may be the national currency of several places."""
    eur = _currency("Q130", id="CurrencyEUR", status="Q122", places=("Q124", "Q125"))
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), eur))
    assert errors(result, "G11") == []


def test_g11_two_currencies_for_two_places_pass() -> None:
    """Two currencies naming different places have no G11 finding."""
    eur = _currency("Q130", id="CurrencyEUR", status="Q122", places=("Q124",))
    dem = _currency("Q131", id="CurrencyDEM", status="Q122", places=("Q125",))
    result = validate.validate(graph(*bench_vocab(), *_currency_vocab(), eur, dem))
    assert errors(result, "G11") == []


def test_g11_place_named_by_two_currencies_is_an_error() -> None:
    """A place two currencies name is G11, reported on the place."""
    eur = _currency("Q130", id="CurrencyEUR", status="Q122", places=("Q124", "Q125"))
    frf = _currency("Q131", id="CurrencyFRF", status="Q122", places=("Q124",))
    vocab = _currency_vocab()
    result = validate.validate(graph(*bench_vocab(), *vocab, eur, frf))
    g11 = errors(result, "G11")
    france = next(e for e in vocab if e.qid == "Q124")
    assert [(f.entity, f.predicate) for f in g11] == [(france, "nationalCurrencyOf")]
    assert g11[0].message.endswith("CurrencyEUR, CurrencyFRF")


def test_g11_no_ops_while_national_currency_of_is_unminted() -> None:
    """With nationalCurrencyOf unminted, G11 is silent."""
    vocab = [e for e in _currency_vocab() if e.qid != "P19"]
    eur = _currency("Q130", id="CurrencyEUR", status="Q122")
    frf = _currency("Q131", id="CurrencyFRF", status="Q122")
    result = validate.validate(graph(*bench_vocab(), *vocab, eur, frf))
    assert errors(result, "G11") == []


def test_g11_not_run_without_the_id_property() -> None:
    """A missing id property blocks G11, since every name it matches is an id."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    result = validate.validate(graph(*vocab, *_currency_vocab()))
    assert "G11" in result.not_run


# --- A2: orphan detection --------------------------------------------------------


def test_a2_referenced_entity_is_not_an_orphan() -> None:
    """A class referenced by a defined property's domainIncludes is not an orphan."""
    financing_activity = entity(
        "Q100",
        id="FinancingActivity",
        label="fa",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q4")]},
    )
    financing_purpose = entity(
        "P50",
        kind=Kind.PROPERTY,
        id="financingPurpose",
        label="fp",
        description="d",
        claims={"P6": [ref("Q100")], "P7": [ref("Q4")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), financing_activity, financing_purpose)
    )
    assert advisories(result, "A2") == []


def test_a2_unreferenced_entity_is_an_orphan() -> None:
    """A value list nothing references, and which references no defined entity, is A2."""
    lonely_enum = entity(
        "Q101",
        id="LonelyEnum",
        label="l",
        description="d",
        claims={"P3": [ref("Q1")], "P4": [ref("Q3")]},
    )
    result = validate.validate(graph(*bench_vocab(), lonely_enum))
    advisory_findings = advisories(result, "A2")
    assert any(f.entity is lonely_enum for f in advisory_findings)
    assert not any(f.rule == "A2" for f in result.errors)
    assert result.ok is True


# --- Keystone: a failure in every layer, one validate() call --------------------


def test_every_layer_fires_in_a_single_validate_call() -> None:
    """One graph carrying a fault in every layer produces findings from every layer."""
    reader_finding = Finding(
        "R2", value="Q999", predicate="P6", message="a quantity datavalue was dropped"
    )
    duplicate_specialization = entity(
        "P60", kind=Kind.PROPERTY, dcid="dcid:specializationOf"
    )
    bad_id_entity = entity(
        "Q110", id="bad-id", label="A", description="d", claims={"P3": [ref("Q4")]}
    )
    related_to = entity("P61", kind=Kind.PROPERTY, dcid="dcid:relatedTo")
    bad_shape_entity = entity(
        "Q111",
        id="BadShapeEntity",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P61": [lit("x")]},
    )
    dangling_prop_entity = entity(
        "Q112",
        id="DanglingPropEntity",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q999")], "P7": [ref("Q4")]},
    )
    result = validate.validate(
        graph(
            *bench_vocab(),
            duplicate_specialization,
            bad_id_entity,
            related_to,
            bad_shape_entity,
            dangling_prop_entity,
            findings=(reader_finding,),
        )
    )
    assert result.ok is False
    rules = {f.rule for f in result.errors}
    assert {"R2", "P2", "I4", "S4", "G1"} <= rules
