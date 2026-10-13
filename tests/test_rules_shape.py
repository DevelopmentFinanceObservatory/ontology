"""Tests for rules/shape.py (S1-S7)."""

from dfo_ontology import config, validate
from dfo_ontology.model import Entity, Kind
from dfo_ontology.shapes import Shape, dispatch

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

# --- S1: reference -----------------------------------------------------------


def test_s1_reference_passes() -> None:
    """A dcid-carrying entity with no statements has no S1 finding."""
    e = entity("Q10", dcid="schema:Foo")
    result = validate.validate(graph(*bench_vocab(), e))
    assert errors(result, "S1") == []


def test_s1_reference_may_be_typed_by_a_class_typed_reference() -> None:
    """A reference typed by another Class-typed reference is clean.

    This is how a country reference says what it is, which is what gives its
    codes a list to sit under in codes.csv.
    """
    country = entity("Q20", dcid="dcid:Country", claims={"P3": [ref("Q1")]})
    afg = entity("Q21", dcid="dcid:country/AFG", claims={"P3": [ref("Q20")]})
    result = validate.validate(graph(*bench_vocab(), country, afg))
    assert errors(result, "S1") == []
    assert errors(result, "G2") == []


def test_s1_reference_typeof_target_must_be_class_typed() -> None:
    """A reference typed by something not typed Class is G2, not S1.

    S1 no longer pins typeOf itself: G2 already asks the same question of every
    entity, and it is the rule that admits an instance as well as a class.
    """
    plain = entity("Q30", id="Plain", label="plain", claims={"P3": [ref("Q4")]})
    e = entity("Q31", dcid="schema:Foo", claims={"P3": [ref("Q30")]})
    result = validate.validate(graph(*bench_vocab(), plain, e))
    assert errors(result, "S1") == []
    g2 = [f for f in errors(result, "G2") if f.entity is e]
    assert len(g2) == 1
    assert g2[0].predicate == "typeOf"


def test_s1_reference_may_carry_codes() -> None:
    """A reference carries the codes that identify it in outside registers."""
    dac = entity("P41", kind=Kind.PROPERTY, id="dacCode")
    country = entity("Q20", dcid="dcid:Country", claims={"P3": [ref("Q1")]})
    afg = entity(
        "Q21",
        dcid="dcid:country/AFG",
        claims={"P3": [ref("Q20")], "P41": [lit("625")]},
    )
    result = validate.validate(graph(*bench_vocab(), dac, country, afg))
    assert errors(result, "S1") == []


def test_s1_reference_may_carry_the_imf_economy_code() -> None:
    """A country, a reference, may state the IMF's code for it."""
    imf = entity("P21", kind=Kind.PROPERTY, id="imfEconomyCode")
    country = entity("Q20", dcid="dcid:Country", claims={"P3": [ref("Q1")]})
    ken = entity(
        "Q21",
        dcid="dcid:country/KEN",
        claims={"P3": [ref("Q20")], "P21": [lit("KEN")]},
    )
    result = validate.validate(graph(*bench_vocab(), imf, country, ken))
    assert errors(result, "S1") == []


def test_s1_reference_disallowed_predicate() -> None:
    """A reference carrying subClassOf, which S1 does not allow, is S1."""
    e = entity("Q10", dcid="schema:Foo", claims={"P4": [ref("Q4")]})
    result = validate.validate(graph(*bench_vocab(), e))
    s1 = errors(result, "S1")
    assert any(f.predicate == "subClassOf" for f in s1)


# --- S2: minted working-set property ------------------------------------------


def test_s2_minted_property_passes() -> None:
    """A property with domain, range, and no typeOf has no S2 finding."""
    e = entity(
        "P9",
        kind=Kind.PROPERTY,
        id="financingPurpose",
        label="A",
        description="d",
        claims={"P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert errors(result, "S2") == []


def test_s2_typeof_gets_the_specific_message() -> None:
    """A minted property stating typeOf gets S2's dedicated message."""
    e = entity(
        "P9",
        kind=Kind.PROPERTY,
        id="financingPurpose",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    s2 = errors(result, "S2")
    typeof_findings = [f for f in s2 if f.predicate == "typeOf"]
    assert len(typeof_findings) == 1
    assert typeof_findings[0].message == (
        "a minted working-set property carries no typeOf; schema:Property is injected"
    )


def test_s2_missing_domain_includes_is_a_cardinality_miss() -> None:
    """A minted property with no domainIncludes is one S2 error naming it."""
    e = entity(
        "P9",
        kind=Kind.PROPERTY,
        id="financingPurpose",
        label="A",
        description="d",
        claims={"P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    s2 = errors(result, "S2")
    assert any(f.predicate == "domainIncludes" for f in s2)


# --- S3: constraint property ---------------------------------------------------


def test_s3_constraint_property_passes() -> None:
    """An item typed Property with domain and range has no S3 finding."""
    e = entity(
        "Q10",
        id="SomeConstraint",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert errors(result, "S3") == []


def test_s3_missing_domain_includes_is_a_cardinality_miss() -> None:
    """A constraint property with no domainIncludes is S3."""
    e = entity(
        "Q10",
        id="SomeConstraint",
        label="A",
        description="d",
        claims={"P3": [ref("Q2")], "P7": [ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    s3 = errors(result, "S3")
    assert any(f.predicate == "domainIncludes" for f in s3)


def test_s3_subproperty_of_stated_twice_is_over_the_cap() -> None:
    """A constraint property stating subPropertyOf twice is over its 0-1 cap."""
    e = entity(
        "Q10",
        id="SomeConstraint",
        label="A",
        description="d",
        claims={
            "P3": [ref("Q2")],
            "P6": [ref("Q4")],
            "P7": [ref("Q4")],
            "P5": [ref("Q2"), ref("Q4")],
        },
    )
    result = validate.validate(graph(*bench_vocab(), e))
    s3 = errors(result, "S3")
    assert any(
        f.predicate == "subPropertyOf" and "at most once" in f.message for f in s3
    )


# --- S4: class or value list ----------------------------------------------------


def test_s4_class_passes() -> None:
    """An item typed Class with no subClassOf has no S4 finding."""
    e = entity(
        "Q10", id="SomeClass", label="A", description="d", claims={"P3": [ref("Q1")]}
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert errors(result, "S4") == []


def test_s4_rejects_a_data_commons_property() -> None:
    """A relatedTo statement fails the gate: the DFO does not mint relatedTo."""
    related_to = entity("P9", kind=Kind.PROPERTY, dcid="dcid:relatedTo")
    e = entity(
        "Q10",
        id="SomeClass",
        label="A",
        description="d",
        claims={"P3": [ref("Q1")], "P9": [lit("x")]},
    )
    result = validate.validate(graph(*bench_vocab(), related_to, e))
    s4 = errors(result, "S4")
    assert len(s4) == 1
    assert s4[0].predicate == "relatedTo"
    assert s4[0].message == "not allowed on a class or value list"


# --- S5: value ------------------------------------------------------------------


def test_s5_value_passes() -> None:
    """An item typed a value list has no S5 finding."""
    value_list = entity(
        "Q11", id="SomeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    e = entity(
        "Q10", id="SomeValue", label="A", description="d", claims={"P3": [ref("Q11")]}
    )
    result = validate.validate(graph(*bench_vocab(), value_list, e))
    assert errors(result, "S5") == []


def test_s5_disallowed_predicate() -> None:
    """A value carrying subClassOf, which S5 does not allow, is S5."""
    value_list = entity(
        "Q11", id="SomeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    e = entity(
        "Q10",
        id="SomeValue",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P4": [ref("Q3")]},
    )
    result = validate.validate(graph(*bench_vocab(), value_list, e))
    s5 = errors(result, "S5")
    assert any(f.predicate == "subClassOf" for f in s5)


def test_s5_classification_code_is_accepted_when_minted() -> None:
    """A minted classificationCode is admitted on a value."""
    code = entity("P9", kind=Kind.PROPERTY, id="classificationCode")
    value_list = entity(
        "Q11", id="SomeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    e = entity(
        "Q10",
        id="SomeValue",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P9": [lit("CODE1")]},
    )
    result = validate.validate(graph(*bench_vocab(), code, value_list, e))
    assert errors(result, "S5") == []


def test_s5_leaves_a_minted_property_to_its_domain() -> None:
    """dacCode on a value is no shape error; a domain of Thing makes it A3 instead."""
    dac = entity(
        "P10",
        kind=Kind.PROPERTY,
        id="dacCode",
        claims={"P6": [ref("Q4")], "P7": [ref("Q4")]},
    )
    value_list = entity(
        "Q11", id="SomeEnum", claims={"P3": [ref("Q1")], "P4": [ref("Q3")]}
    )
    e = entity(
        "Q10",
        id="SomeValue",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P10": [lit("913")]},
    )
    result = validate.validate(graph(*bench_vocab(), dac, value_list, e))
    assert errors(result, "S5") == []
    assert [f.entity for f in advisories(result, "A3")] == [e]


# --- S6: individual ---------------------------------------------------------------


def test_s6_individual_passes() -> None:
    """An item typed a class reaching Thing has no S6 finding."""
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeIndividual",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")]},
    )
    result = validate.validate(graph(*bench_vocab(), a_class, e))
    assert errors(result, "S6") == []


def test_s6_rejects_anything_beyond_typeof() -> None:
    """An individual carrying specializationOf beyond typeOf is S6."""
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeIndividual",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P8": [lit("x")]},
    )
    result = validate.validate(graph(*bench_vocab(), a_class, e))
    s6 = errors(result, "S6")
    assert any(f.predicate == "specializationOf" for f in s6)


def test_s6_daccode_is_accepted_when_minted() -> None:
    """A minted dacCode is admitted on an individual."""
    dac = entity("P10", kind=Kind.PROPERTY, id="dacCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeIndividual",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P10": [lit("913")]},
    )
    result = validate.validate(graph(*bench_vocab(), dac, a_class, e))
    assert errors(result, "S6") == []


def test_s6_daccode_may_be_stated_more_than_once() -> None:
    """A register can reach one thing through more than one code."""
    dac = entity("P10", kind=Kind.PROPERTY, id="dacCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeIndividual",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P10": [lit("11"), lit("70")]},
    )
    result = validate.validate(graph(*bench_vocab(), dac, a_class, e))
    assert errors(result, "S6") == []


def test_s6_carries_the_currency_properties() -> None:
    """An individual may state the ISO codes and the currency status."""
    alpha = entity("P11", kind=Kind.PROPERTY, id="iso4217AlphaCode")
    numeric = entity("P12", kind=Kind.PROPERTY, id="iso4217NumericCode")
    status = entity("P13", kind=Kind.PROPERTY, id="currencyStatus")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    status_value = entity("Q12", id="CurrencyStatusCurrent", claims={"P3": [ref("Q1")]})
    e = entity(
        "Q10",
        id="CurrencyUSD",
        label="US Dollar",
        description="d",
        claims={
            "P3": [ref("Q11")],
            "P11": [lit("USD")],
            "P12": [lit("840")],
            "P13": [ref("Q12")],
        },
    )
    graph_ = graph(*bench_vocab(), alpha, numeric, status, a_class, status_value, e)
    result = validate.validate(graph_)
    assert errors(result, "S6") == []


def test_s6_carries_national_currency_of_more_than_once() -> None:
    """An individual may name several places through nationalCurrencyOf."""
    national = entity("P18", kind=Kind.PROPERTY, id="nationalCurrencyOf")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    france = entity("Q12", id="France", claims={"P3": [ref("Q11")]})
    germany = entity("Q13", id="Germany", claims={"P3": [ref("Q11")]})
    e = entity(
        "Q10",
        id="CurrencyEUR",
        label="Euro",
        description="d",
        claims={"P3": [ref("Q11")], "P18": [ref("Q12"), ref("Q13")]},
    )
    graph_ = graph(*bench_vocab(), national, a_class, france, germany, e)
    result = validate.validate(graph_)
    assert errors(result, "S6") == []


def test_s6_iso_alpha_code_at_most_once() -> None:
    """A currency has one ISO alphabetic code, unlike its DAC codes."""
    alpha = entity("P11", kind=Kind.PROPERTY, id="iso4217AlphaCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="CurrencyUSD",
        label="US Dollar",
        description="d",
        claims={"P3": [ref("Q11")], "P11": [lit("USD"), lit("USS")]},
    )
    result = validate.validate(graph(*bench_vocab(), alpha, a_class, e))
    s6 = errors(result, "S6")
    assert any(f.predicate == "iso4217AlphaCode" for f in s6)


def test_s6_carries_the_world_bank_codes() -> None:
    """An individual may state the World Bank economy and counterpart codes."""
    counterpart = entity("P15", kind=Kind.PROPERTY, id="wbCounterpartCode")
    economy = entity("P16", kind=Kind.PROPERTY, id="wbEconomyCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeCountry",
        label="France",
        description="d",
        claims={"P3": [ref("Q11")], "P15": [lit("004")], "P16": [lit("FRA")]},
    )
    result = validate.validate(graph(*bench_vocab(), counterpart, economy, a_class, e))
    assert errors(result, "S6") == []


def test_s6_world_bank_codes_at_most_once() -> None:
    """Each World Bank list names an entity once, unlike the DAC register."""
    counterpart = entity("P15", kind=Kind.PROPERTY, id="wbCounterpartCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeCountry",
        label="France",
        description="d",
        claims={"P3": [ref("Q11")], "P15": [lit("004"), lit("005")]},
    )
    result = validate.validate(graph(*bench_vocab(), counterpart, a_class, e))
    assert any(f.predicate == "wbCounterpartCode" for f in errors(result, "S6"))


def test_s6_carries_the_m49_code() -> None:
    """An individual may state its UN M49 code."""
    m49 = entity("P18", kind=Kind.PROPERTY, id="m49Code")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="M49NorthernAfrica",
        label="Northern Africa (UN M49)",
        description="d",
        claims={"P3": [ref("Q11")], "P18": [lit("015")]},
    )
    result = validate.validate(graph(*bench_vocab(), m49, a_class, e))
    assert errors(result, "S6") == []


def test_s6_m49_code_at_most_once() -> None:
    """M49 assigns one code per country, area or region."""
    m49 = entity("P18", kind=Kind.PROPERTY, id="m49Code")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="M49NorthernAfrica",
        label="Northern Africa (UN M49)",
        description="d",
        claims={"P3": [ref("Q11")], "P18": [lit("015"), lit("202")]},
    )
    result = validate.validate(graph(*bench_vocab(), m49, a_class, e))
    assert any(f.predicate == "m49Code" for f in errors(result, "S6"))


def test_s6_carries_the_imf_economy_code() -> None:
    """An individual may state its IMF economy code."""
    imf = entity("P21", kind=Kind.PROPERTY, id="imfEconomyCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="IMFSubSaharanAfrica",
        label="Sub-Saharan Africa (IMF)",
        description="d",
        claims={"P3": [ref("Q11")], "P21": [lit("G603")]},
    )
    result = validate.validate(graph(*bench_vocab(), imf, a_class, e))
    assert errors(result, "S6") == []


def test_s6_imf_economy_code_at_most_once() -> None:
    """The IMF assigns one code per economy or group of economies."""
    imf = entity("P21", kind=Kind.PROPERTY, id="imfEconomyCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="IMFSubSaharanAfrica",
        label="Sub-Saharan Africa (IMF)",
        description="d",
        claims={"P3": [ref("Q11")], "P21": [lit("G603"), lit("G001")]},
    )
    result = validate.validate(graph(*bench_vocab(), imf, a_class, e))
    assert any(f.predicate == "imfEconomyCode" for f in errors(result, "S6"))


def test_s6_states_its_members() -> None:
    """A grouping lists every member, so hasMember is uncapped."""
    has_member = entity("P17", kind=Kind.PROPERTY, id="hasMember")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    member = entity(
        "Q12", id="SomeCountry", label="c", description="d", claims={"P3": [ref("Q11")]}
    )
    e = entity(
        "Q10",
        id="SomeGrouping",
        label="g",
        description="d",
        claims={"P3": [ref("Q11")], "P17": [ref("Q12"), ref("Q12")]},
    )
    result = validate.validate(graph(*bench_vocab(), has_member, a_class, member, e))
    assert errors(result, "S6") == []


def test_daccode_is_accepted_on_an_entity_typed_to_a_reference() -> None:
    """An entity typed to a bare reference may still carry dacCode.

    This is the shape the organisation entities take: `Organization` is a
    reference carrying only its dcid and `instance of → Class`, so the chain
    dead-ends and the entity is indeterminate rather than an individual. A
    minted property is admitted either way, so the row still reaches codes.csv.
    """
    dac = entity("P10", kind=Kind.PROPERTY, id="dacCode")
    organization = entity("Q12", dcid="dcid:Organization", claims={"P3": [ref("Q1")]})
    e = entity(
        "Q10",
        id="SomeOrg",
        label="A",
        description="d",
        claims={"P3": [ref("Q12")], "P10": [lit("913")]},
    )
    result = validate.validate(graph(*bench_vocab(), dac, organization, e))
    assert errors(result, "S5|S6") == []


def test_currency_properties_pass_on_the_merged_shape() -> None:
    """The currency properties pass on the value-or-individual shape.

    An individual whose class hangs under a reference dead-ends its chain and
    dispatches to the merged shape, which is how the currencies on both
    benches are shaped.
    """
    alpha = entity("P11", kind=Kind.PROPERTY, id="iso4217AlphaCode")
    numeric = entity("P12", kind=Kind.PROPERTY, id="iso4217NumericCode")
    status = entity("P13", kind=Kind.PROPERTY, id="currencyStatus")
    dac = entity("P10", kind=Kind.PROPERTY, id="dacCode")
    unit_of_measure = entity(
        "Q13", dcid="dcid:UnitOfMeasure", claims={"P3": [ref("Q1")]}
    )
    currency_class = entity(
        "Q11", id="CurrencyUnit", claims={"P3": [ref("Q1")], "P4": [ref("Q13")]}
    )
    status_value = entity("Q12", id="CurrencyStatusCurrent", claims={"P3": [ref("Q1")]})
    e = entity(
        "Q10",
        id="CurrencyCHF",
        label="Swiss Franc",
        description="d",
        claims={
            "P3": [ref("Q11")],
            "P10": [lit("11"), lit("70")],
            "P11": [lit("CHF")],
            "P12": [lit("756")],
            "P13": [ref("Q12")],
        },
    )
    result = validate.validate(
        graph(
            *bench_vocab(),
            alpha,
            numeric,
            status,
            dac,
            unit_of_measure,
            currency_class,
            status_value,
            e,
        )
    )
    assert errors(result, "S5|S6") == []


# --- S5|S6: blind discrimination ---------------------------------------------------


def test_s5_or_s6_blind_checks_the_union_without_a_skip() -> None:
    """A chain stopping at a reference checks the union allowlist and records no skip."""
    code = entity("P9", kind=Kind.PROPERTY, id="classificationCode")
    reference = entity("Q12", dcid="schema:Organization")
    ambiguous_class = entity(
        "Q11", id="Ambiguous", claims={"P3": [ref("Q1")], "P4": [ref("Q12")]}
    )
    e = entity(
        "Q10",
        id="MaybeValueOrIndividual",
        label="A",
        description="d",
        claims={"P3": [ref("Q11")], "P9": [lit("CODE1")]},
    )
    result = validate.validate(
        graph(*bench_vocab(), code, reference, ambiguous_class, e)
    )
    assert not any(f.entity is e for f in result.errors)
    assert result.skips == []


# --- S7: undetermined shape ---------------------------------------------------------


def test_s7_typeof_absent() -> None:
    """An id-carrying item with no typeOf is S7, not skipped."""
    e = entity("Q10", id="NoType", label="A", description="d")
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.entity is e for f in errors(result, "S7"))
    assert not any(f.entity is e for f in skips(result, "S7"))


def test_s7_typeof_multiple() -> None:
    """An id-carrying item with two typeOf statements is S7, not skipped."""
    e = entity(
        "Q10",
        id="TwoTypes",
        label="A",
        description="d",
        claims={"P3": [ref("Q1"), ref("Q4")]},
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert any(f.entity is e for f in errors(result, "S7"))
    assert not any(f.entity is e for f in skips(result, "S7"))


def test_s7_typeof_unresolvable() -> None:
    """An id-carrying item with a dangling typeOf is a skip, not an S7 error.

    G1 reports the dangling reference itself; the shape layer skips rather
    than reporting the same fault a second time.
    """
    e = entity(
        "Q10", id="Dangling", label="A", description="d", claims={"P3": [ref("Q999")]}
    )
    result = validate.validate(graph(*bench_vocab(), e))
    assert not any(f.entity is e for f in errors(result, "S7"))
    assert any(f.entity is e for f in skips(result, "S7"))


def test_dangling_typeof_reports_once_as_g1_plus_one_skip() -> None:
    """A dangling typeOf yields exactly one error (G1) and one skip, not two errors."""
    e = entity(
        "Q10", id="Dangling", label="A", description="d", claims={"P3": [ref("Q999")]}
    )
    result = validate.validate(graph(*bench_vocab(), e))
    entity_errors = [f for f in result.errors if f.entity is e]
    entity_skips = [f for f in result.skips if f.entity is e]
    assert [f.rule for f in entity_errors] == ["G1"]
    assert [f.rule for f in entity_skips] == ["S7"]


# --- cycles: skip, not an S7 error ----------------------------------------------------


def test_typeof_target_in_a_cycle_produces_a_skip_not_an_error() -> None:
    """A typeOf target caught in a subClassOf cycle is a skip, since G8 reports the cycle."""
    a = entity("Q10", id="CycleA", claims={"P3": [ref("Q1")], "P4": [ref("Q11")]})
    b = entity("Q11", id="CycleB", claims={"P3": [ref("Q1")], "P4": [ref("Q10")]})
    e = entity(
        "Q12", id="UsesCycle", label="A", description="d", claims={"P3": [ref("Q10")]}
    )
    result = validate.validate(graph(*bench_vocab(), a, b, e))
    assert not any(f.entity is e for f in errors(result, "S7"))
    assert any(f.entity is e for f in skips(result, "S7"))


def test_cycle_skip_reason_covers_both_hierarchy_predicates() -> None:
    """The reason names both predicates `cyclic` is built from, not just subClassOf.

    Here the typeOf target is a property item in a subPropertyOf cycle, so a
    reason naming only subClassOf would point at a predicate not involved.
    """
    a = entity("Q10", kind=Kind.PROPERTY, id="cycleA", claims={"P5": [ref("Q11")]})
    b = entity("Q11", kind=Kind.PROPERTY, id="cycleB", claims={"P5": [ref("Q10")]})
    e = entity(
        "Q12", id="UsesCycle", label="A", description="d", claims={"P3": [ref("Q10")]}
    )
    result = validate.validate(graph(*bench_vocab(), a, b, e))
    skip = next(f for f in skips(result, "S7") if f.entity is e)
    assert "subPropertyOf" in skip.message


# --- preflight gaps guard the shape layer per-shape, not the layer as a whole -----


def test_missing_id_property_blocks_s7_instead_of_firing_per_entity() -> None:
    """A missing id property blocks S7, so an untyped entity produces no S7 finding."""
    vocab = [e for e in bench_vocab() if e.qid != "P1"]
    untyped = entity("Q10", id="NoType", label="A", description="d")
    result = validate.validate(graph(*vocab, untyped))
    assert not any(f.rule == "S7" for f in result.errors)
    assert not any(f.rule == "S7" for f in result.skips)


# --- minted properties --------------------------------------------------------


def test_a_newly_minted_property_needs_no_shape_change() -> None:
    """A property just minted on the bench compiles on an individual, as often as stated."""
    region_code = entity("P50", kind=Kind.PROPERTY, id="oecdRegionCode")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeRegion",
        label="r",
        description="d",
        claims={"P3": [ref("Q11")], "P50": [lit("A1"), lit("A2")]},
    )
    result = validate.validate(graph(*bench_vocab(), region_code, a_class, e))
    assert errors(result, "S6") == []


def test_a_data_commons_property_stays_rejected() -> None:
    """A reused Data Commons property has no domain on the bench, so it is S6."""
    contained = entity("P50", kind=Kind.PROPERTY, dcid="dcid:containedInPlace")
    a_class = entity(
        "Q11", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q10",
        id="SomeRegion",
        label="r",
        description="d",
        claims={"P3": [ref("Q11")], "P50": [ref("Q11")]},
    )
    result = validate.validate(graph(*bench_vocab(), contained, a_class, e))
    assert [(f.predicate, f.message) for f in errors(result, "S6")] == [
        ("containedInPlace", "not allowed on an individual")
    ]


def test_s1_reference_rejects_a_property_codes_csv_does_not_read() -> None:
    """A reference emits no node, so anything but a code on it would be lost."""
    national = entity("P18", kind=Kind.PROPERTY, id="nationalCurrencyOf")
    e = entity("Q10", dcid="dcid:country/FRA", claims={"P18": [ref("Q10")]})
    result = validate.validate(graph(*bench_vocab(), national, e))
    assert [(f.predicate, f.message) for f in errors(result, "S1")] == [
        (
            "nationalCurrencyOf",
            "a reference emits no node, so it may carry only the code properties "
            "codes.csv reads",
        )
    ]


def test_s1_reference_holds_a_single_valued_code_to_one() -> None:
    """The one-per-node codes are capped on a reference as on a DFO node."""
    imf = entity("P21", kind=Kind.PROPERTY, id="imfEconomyCode")
    e = entity("Q10", dcid="dcid:country/KEN", claims={"P21": [lit("664"), lit("KEN")]})
    result = validate.validate(graph(*bench_vocab(), imf, e))
    assert [(f.predicate, f.message) for f in errors(result, "S1")] == [
        ("imfEconomyCode", "must be stated at most once")
    ]


def test_every_code_property_may_sit_on_a_reference() -> None:
    """Each property codes.csv reads is admitted on a reference once minted."""
    minted = [
        entity(f"P{50 + i}", kind=Kind.PROPERTY, id=name)
        for i, name in enumerate(config.CODE_PROPERTY_IDS)
    ]
    e = entity(
        "Q10",
        dcid="dcid:country/KEN",
        claims={prop.qid or "": [lit("1")] for prop in minted},
    )
    result = validate.validate(graph(*bench_vocab(), *minted, e))
    assert errors(result, "S1") == []


# --- isProvisional -------------------------------------------------------------


def _provisional_vocab() -> list[Entity]:
    """The isProvisional property and the True node it points at."""
    return [
        entity("P30", kind=Kind.PROPERTY, dcid="dcid:isProvisional"),
        entity("Q30", dcid="schema:True"),
    ]


def test_is_provisional_once_on_every_dfo_shape() -> None:
    """Any node the DFO emits may be flagged provisional once."""
    flag = {"P30": [ref("Q30")]}
    nodes = [
        entity(
            "P31",
            kind=Kind.PROPERTY,
            id="someProperty",
            label="p",
            description="d",
            claims={"P6": [ref("Q10")], "P7": [ref("Q10")], **flag},
        ),
        entity(
            "Q10",
            id="SomeClass",
            label="c",
            description="d",
            claims={"P3": [ref("Q1")], "P4": [ref("Q4")], **flag},
        ),
        entity(
            "Q11",
            id="someConstraint",
            label="k",
            description="d",
            claims={"P3": [ref("Q2")], "P6": [ref("Q10")], "P7": [ref("Q12")], **flag},
        ),
        entity(
            "Q12",
            id="SomeEnum",
            label="l",
            description="d",
            claims={"P3": [ref("Q1")], "P4": [ref("Q3")], **flag},
        ),
        entity(
            "Q13",
            id="SomeValue",
            label="v",
            description="d",
            claims={"P3": [ref("Q12")], **flag},
        ),
        entity(
            "Q14",
            id="SomeIndividual",
            label="i",
            description="d",
            claims={"P3": [ref("Q10")], **flag},
        ),
    ]
    g = graph(*bench_vocab(), *_provisional_vocab(), *nodes)
    assert {dispatch(g, n).shape for n in nodes} == {
        Shape.MINTED_PROPERTY,
        Shape.CONSTRAINT_PROPERTY,
        Shape.CLASS_OR_LIST,
        Shape.VALUE,
        Shape.INDIVIDUAL,
    }
    assert validate.validate(g).errors == []


def test_is_provisional_at_most_once() -> None:
    """A node is flagged once or not at all."""
    a_class = entity(
        "Q10", id="SomeClass", claims={"P3": [ref("Q1")], "P4": [ref("Q4")]}
    )
    e = entity(
        "Q11",
        id="SomeIndividual",
        label="i",
        description="d",
        claims={"P3": [ref("Q10")], "P30": [ref("Q30"), ref("Q30")]},
    )
    result = validate.validate(graph(*bench_vocab(), *_provisional_vocab(), a_class, e))
    assert any(f.predicate == "isProvisional" for f in errors(result, "S6"))


def test_is_provisional_is_not_allowed_on_a_reference() -> None:
    """A reference emits no node, so it has nothing to flag."""
    e = entity("Q10", dcid="dcid:country/FRA", claims={"P30": [ref("Q30")]})
    result = validate.validate(graph(*bench_vocab(), *_provisional_vocab(), e))
    assert any(f.predicate == "isProvisional" for f in errors(result, "S1"))
