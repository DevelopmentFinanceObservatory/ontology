# Validation rulebook

You land here from a `report.txt` footer after `dfo-ontology compile` failed, or
because a successful run still printed a skip or an advisory. This page covers
every rule id the compiler can print, grouped by the layer that runs it: reader,
preflight, identity, shape, graph, emission, then the advisories. The bench is
the Wikibase instance a run reads, named by `--bench`.

## Outcome kinds

Every finding is one of three kinds, and the report groups them accordingly:

- **Error.** Blocks emission. No `dfo.mcf` is written while any error exists,
  regardless of layer. Errors appear under the entity they belong to, or under
  `Cross-entity` when no single entity owns the fault (a duplicate id, a
  `subClassOf` cycle).
- **Skip.** The check could not run for one entity. Usually a node it depends
  on has no local `typeOf` to read, most often a global node carrying a `dcid`
  and nothing else, so the compiler cannot see far enough into a node it does not
  own. Otherwise another rule already reports the cause (see S7). A skip is not
  a pass and not a failure. Skips are listed under `Skipped checks` and never
  block emission.
- **Advisory.** Reported, never blocking. Advisories are listed under
  `Advisories` in every report, failing or passing.

A fourth line, `Not run: <ids>`, is different from a skip: it means a whole
rule could not run at all, for every entity, because something the rule
depends on is missing from the bench, claimed twice on it, or set up wrongly
(see [Preflight](#preflight-p1p3)).

## Reader (R1–R3)

The reader turns each `wbgetentities` payload into an entity. These findings
fire while parsing, before any layer runs.

| id  | checks                                                                                                           | fix                                                                                                                                                                              |
| --- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | a statement's snak carries no value (`novalue` or `somevalue`)                                                   | State an actual value, or remove the statement. The statement is dropped either way, so nothing downstream sees it.                                                              |
| R2  | a statement's datavalue is a type the compiler does not read — quantity, time, monolingualtext, globe-coordinate | Restate the fact as a Wikibase item reference or a plain string. Only entity references and strings compile.                                                                     |
| R3  | a `wbgetentities` entry came back marked missing                                                                 | The entity was deleted, or you fetched a qid that no longer exists. If it should exist, recreate it; if a statement still points at it, that reference is now dangling (see G1). |

## Preflight (P1–P3)

Preflight checks the bench's own bookkeeping vocabulary before any per-entity
rule runs, so one missing piece produces one finding instead of one per
entity. When a preflight check fails, the rules that depend on it are listed
under `Not run` rather than firing per entity.

| id  | checks                                                                                                                                                        | fix                                                                                                                                                                                                                        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | the id property and the dcid property both exist and are Wikibase properties                                                                                  | Create the missing property on the bench. Every bench expects it at `P1` and `P2`; a bench that numbered them differently needs a `config.py` change.                                                                      |
| P2  | each structural predicate (`typeOf`, `subClassOf`, `subPropertyOf`, `domainIncludes`, `rangeIncludes`, `specializationOf`) is claimed by at most one property | Two properties resolve to the same predicate name. A property's name is its `dcid` without the prefix, or its `id` when it has no `dcid`, so `schema:typeOf` and `dcid:typeOf` collide. Remove the claim from one of them. |
| P3  | the four well-known items — Class, Property, Thing, Enumeration — each exist exactly once                                                                     | Create the missing item, or resolve the duplicate: two items carry a dcid with the same name after the prefix, such as `schema:Class` and `dcid:Class` (or whichever name P3 names).                                       |

## Identity (I1–I11)

Every id-carrying or dcid-carrying entity goes through these. Findings name
the entity and, where relevant, the offending value.

| id  | checks                                                                                                                                                               | fix                                                                                                                                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I1  | exactly one of `id` / `dcid` is stated                                                                                                                               | Give the entity one identifier. "carries neither id nor dcid" means it has no statement through either bookkeeping property; "carries both id and dcid" means it has both — pick one.                                                                                                              |
| I2  | `id` and `dcid` are each stated at most once                                                                                                                         | Remove the extra statement; keep one.                                                                                                                                                                                                                                                              |
| I3  | the id property and the dcid property themselves carry no identifier                                                                                                 | The bookkeeping property (P1 or P2) has an `id` or `dcid` statement on itself. Bookkeeping properties are not concepts — remove the statement.                                                                                                                                                     |
| I4  | `id` is a local name of letters and digits, optionally under a lowercase namespace segment — `Afghanistan`, or `country/PacificIslandsUS`                            | Rename the id to start with a letter and use only letters and digits — no hyphens, underscores, or spaces. One namespace segment is allowed, lowercase-initial and followed by a single slash, for a node minted into a Data Commons namespace so it sits beside the global nodes it belongs with. |
| I5  | `id` is unique across the whole bench                                                                                                                                | The same id is stated on more than one entity, listed by qid in the finding. Rename one of them.                                                                                                                                                                                                   |
| I6  | `dcid` carries a prefix (`schema:`, `dcid:`, …) and is unique across the bench                                                                                       | "must carry a prefix" — add the namespace prefix the global node actually uses. "duplicate dcid" — two entities claim the same global node; only one reference to it should exist.                                                                                                                 |
| I7  | the emitted dcid — the prefix and the id together — is at most 256 characters                                                                                        | Shorten the id.                                                                                                                                                                                                                                                                                    |
| I8  | every emitted value — `name`, `description`, `alternateName`, and any literal statement — is at most 65,535 characters after quote-escaping                          | Shorten the value. The limit is the Data Commons importer's, not this compiler's.                                                                                                                                                                                                                  |
| I9  | id casing matches the identifier's kind, judged on the local name: a property id starts lowercase, every other id starts uppercase, a value list's id ends in `Enum` | Rename the id to match its shape. A property whose id starts uppercase, or a class/value/individual id that starts lowercase, is renamed. A value list (a class whose `subClassOf` chain reaches Enumeration) needs its id to end in `Enum`.                                                       |
| I10 | every id-carrying entity has an English label                                                                                                                        | Add an English label. A node with no label would emit with no `name`, which is why this is an error and not an advisory.                                                                                                                                                                           |
| I11 | no emitted value — `name`, `description`, `alternateName`, or any literal statement — contains a backslash                                                           | Remove the backslash. MCF documents `\"` as the escape for a quote but says nothing about a bare backslash, so it cannot be represented safely — this gates rather than guessing at unverified unescaping behaviour.                                                                               |

## Shape (S1–S7)

Shape is an **allowlist** for the statements that build the graph: `typeOf`,
`subClassOf`, `subPropertyOf`, `domainIncludes`, `rangeIncludes`,
`specializationOf` and `isProvisional`. Each shape lists which of them it may
carry and how often, and a statement the matched shape does not list is rejected.

A statement made through a property the DFO mints is different. It may sit on
any node the DFO emits, and no list here decides whether it belongs there: the
property's own `domainIncludes` and `rangeIncludes` do, through
[A3 and A4](#advisories-a1a4). A newly minted property therefore compiles on
its first run. Most may be stated any number of times. A few hold one value per
node, such as the ISO currency codes and the M49 code, and a second statement
is a cardinality miss; `SINGLE_VALUED` in `rules/shape.py` names them. A Data
Commons property reused on the bench is rejected unless a shape lists it,
because its domain and range live in Data Commons, where nothing here can
check them.

An entity's shape is not declared — it is dispatched, in this order, from what
the entity itself carries:

1. It carries a `dcid` → a **reference** to a node outside the DFO.
1. It has an `id` and lives in the property namespace → a **minted
   working-set property**.
1. Its `typeOf` resolves to the Property item → a **constraint property**.
1. Its `typeOf` resolves to the Class item → a **class or value list**.
1. Its `typeOf` resolves to something whose own `subClassOf` chain reaches
   Enumeration → a **value**.
1. Its `typeOf` resolves to something whose chain reaches Thing → an
   **individual**.
1. Its `typeOf` resolves to something whose chain stops at a reference other
   than Thing or Enumeration → a **value or individual**, which the compiler
   cannot tell apart (see S5|S6 below).
1. Anything else — no identifier, `typeOf` absent, stated more than once,
   unresolvable, or its chain reaches both Thing and Enumeration, or neither —
   is **undetermined**, and none of the S1–S6 checks run for it.

`id` and `dcid` statements are exempt from every allowlist below — they are
the bookkeeping that makes the dispatch above possible in the first place, not
a fact the shape describes.

| shape                       | id  | may carry                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------- | --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reference                   | S1  | an optional `typeOf`, and any code property once it is minted on the bench: the properties `CODE_PROPERTY_IDS` in `config.py` lists, which are the ones codes.csv reads. The reference emits no node, so its codes reach nobody through the MCF — they reach a consumer through codes.csv, which is the whole reason for stating them. Any other minted property is rejected, since nothing would carry it anywhere. Where the `typeOf` may point is G2's question, not S1's |
| Minted working-set property | S2  | `domainIncludes` (one or more), `rangeIncludes` (one or more), `subPropertyOf` (at most one), `isProvisional` (at most one) — and no `typeOf` at all; the compiler injects `schema:Property` on emission, so stating one yourself is rejected                                                                                                                                                                                                                                |
| Constraint property         | S3  | `typeOf` (exactly one), `domainIncludes` (one or more), `rangeIncludes` (one or more), `subPropertyOf` (at most one), `isProvisional` (at most one)                                                                                                                                                                                                                                                                                                                          |
| Class or value list         | S4  | `typeOf` (exactly one), `subClassOf` (any number), `isProvisional` (at most one)                                                                                                                                                                                                                                                                                                                                                                                             |
| Value                       | S5  | `typeOf` (exactly one), `specializationOf` (at most one), `isProvisional` (at most one)                                                                                                                                                                                                                                                                                                                                                                                      |
| Individual                  | S6  | `typeOf` (exactly one), `isProvisional` (at most one). Which entities may carry `nationalCurrencyOf`, and how many may name one place, are G10 and G11's questions                                                                                                                                                                                                                                                                                                           |

`isProvisional` flags a node that is not yet final: its name, description or
place in the model may still change. Point it at Data Commons' `True` (a
reference carrying `schema:True`) and delete the statement once the node is
settled; do not state `False`. Every node the DFO emits may carry it once. A
reference emits nothing, so it may not. A passing run lists every
provisional node in `report.txt`.

Two kinds of shape finding:

- **A disallowed predicate** — a statement made through a predicate the matched
  shape's list does not carry. The finding names the predicate and the shape,
  e.g. "not allowed on a value". Remove the statement, or reconsider whether
  the entity is really this shape. A minted property other than a code, stated
  on a reference, says instead that a reference carries only codes.
- **A cardinality miss** — a listed predicate stated too few or too many
  times: "must be stated exactly once", "must be stated at least once" or
  "must be stated at most once". Add or remove statements until the count
  matches.

**S7 — undetermined.** Fires whenever `typeOf` does not resolve cleanly, or the
entity has no identifier at all. As an
error, the message names the cause: `typeOf is absent`, `typeOf is stated more than once`, `typeOf does not reference an entity`, or the chain reaches both Thing and Enumeration, or neither. Fix by
stating exactly one `typeOf`, pointing at something whose own chain resolves.
Some S7 causes are recorded as a skip instead — a dangling `typeOf` target
(G1 already reports the dangling reference), a `typeOf` target caught in a
`subClassOf` or `subPropertyOf` cycle (G8 already reports the cycle, and names
which predicate it was), or a bench missing one of the Property, Class, Thing,
or Enumeration well-known items (P3 already reports that), or an entity that
carries neither `id` nor `dcid` (I1 already reports that).

**S5|S6 — indeterminate.** When `typeOf` resolves to something whose
`subClassOf` chain stops at a reference other than Thing or Enumeration — an
organisation typed to Organization, say — the compiler cannot tell a value from
an individual, and does not guess. It checks the entity against the union of
both allowlists, and the report counts it as `indeterminate`. That is not a
fault: the chain has reached a node Data Commons owns, so there is nothing more
to state.

## Graph (G1–G11)

Whole-graph checks: what a statement's target is, and what the graph looks
like once every entity is in it.

| id  | checks                                                                                                                                                                                                                                                                                                   | fix                                                                                                                                                                                                                                                                                                                                                                                               |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | every referenced target exists in the bench                                                                                                                                                                                                                                                              | Create the missing entity, or remove the dangling statement. This is the only rule that reports a dangling reference — every other rule reaches targets through resolved edges only, so a dangling one cannot reach them.                                                                                                                                                                         |
| G2  | a `typeOf` target is the Class item itself, or an item itself typed Class                                                                                                                                                                                                                                | Point `typeOf` at Class, or at something typed Class. "target carries no local typing" is a skip: the target has no single `typeOf` to read. That is normally a bare reference, whose typing lives in Data Commons; a DFO node in that state also gets its own S7 error.                                                                                                                          |
| G3  | a `domainIncludes` target is typed Class                                                                                                                                                                                                                                                                 | Point it at a Class-typed item. What a property describes is always an entity, so a data type is not admitted here. Skipped, not failed, when the target has no single `typeOf` to read, normally because it is a bare reference whose typing lives in Data Commons.                                                                                                                              |
| G4  | a `rangeIncludes` target is typed Class or DataType                                                                                                                                                                                                                                                      | Point it at a Class-typed item, or at a data type. This is what covers primitive ranges: Data Commons types `Text`, `Number` and `Date` as DataType rather than Class, and the bench states that typing. Skipped, not failed, when the target has no single `typeOf` to read, normally because it is a bare reference.                                                                            |
| G5  | every id-carrying class reaches exactly one of Thing or Enumeration through its `subClassOf` chain                                                                                                                                                                                                       | "reaches both" or "reaches neither" is an error — add or remove `subClassOf` statements until the chain resolves to exactly one root. A chain that stops at any other reference, such as Organization, passes: that node belongs to Data Commons, so its own parents are not checked. Scoped to id-carrying classes, so reference items never fire this. A class caught in a cycle is left to G8. |
| G6  | a `subPropertyOf` target is itself a property                                                                                                                                                                                                                                                            | Point it at a Wikibase property, or at an item typed Property.                                                                                                                                                                                                                                                                                                                                    |
| G7  | a `specializationOf` target shares the same `typeOf` target as the source — asserted positively, not just "not stated to be elsewhere"                                                                                                                                                                   | Point `specializationOf` at a value in the same list (the same `typeOf` target), or fix whichever side's `typeOf` does not resolve.                                                                                                                                                                                                                                                               |
| G8  | no cycles in `subClassOf`, `subPropertyOf`, or `specializationOf`                                                                                                                                                                                                                                        | Break the cycle — one of the entities listed needs to point somewhere outside the loop. All three predicates form hierarchies, so a loop states that two entities are each narrower than the other. Reported once per cycle, per predicate, under `Cross-entity`, naming every member.                                                                                                            |
| G9  | `classificationCode` is stated only on values (or on a value-or-individual, S5\|S6), and is unique within its value list. Every other code property in `CODE_PROPERTY_IDS` is deliberately outside this rule: each records a code a thing carries in someone else's register, where duplicates are legal | "only allowed on a value" — remove the statement from a non-value entity. "duplicate classificationCode" — give one of the listed entities a different code. No-ops while `classificationCode` is not yet minted on the bench.                                                                                                                                                                    |
| G10 | `nationalCurrencyOf` is stated only on a currency whose `currencyStatus` is `CurrencyStatusCurrent`                                                                                                                                                                                                      | Move the `nationalCurrencyOf` statements from a withdrawn currency to the currency that replaced it, or set `currencyStatus` to `CurrencyStatusCurrent` if the currency is still in use. A currency with no `currencyStatus`, or whose status target does not exist, counts as not current. No-ops while `nationalCurrencyOf` is not minted on the bench.                                         |
| G11 | no place is named through `nationalCurrencyOf` by more than one currency                                                                                                                                                                                                                                 | Remove the statement from every currency but the place's national one: the currency its central bank or currency union issues, or the foreign currency it adopted. A currency that only circulates alongside it does not count. Reported on the place, naming each currency. No-ops while `nationalCurrencyOf` is not minted on the bench.                                                        |

## Emission (E1)

Runs only when `compile` is given `--exclude-provisional`, which leaves every
provisional node out of the MCF and codes.csv. Leaving a node out must not
leave a node that stays in pointing at it. A coded reference stays in too: it
emits no node, but its codes.csv row names the list its `typeOf` points at.

| id  | checks                                                                                                                    | fix                                                                                                                                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1  | no node left in the MCF, and no coded reference, points at a provisional node or is stated through a provisional property | Flag the dependent node provisional too, settle the node it depends on by deleting its `isProvisional` statement, or compile without `--exclude-provisional`. A reference cannot be flagged, so settle what it points at instead. |

## Advisories (A1–A4)

Never block emission. They print on an otherwise successful run, so a clean
compile can still carry a suggestion.

| id  | checks                                                                                                                                                                                                                                                                                                        | fix                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | an id-carrying entity has no English description                                                                                                                                                                                                                                                              | Add one. Unlike a missing label (I10), this does not stop the node from emitting — it is a content-review concern, not a structural one.                                                                                                                                                                                                                                                                                                                                                    |
| A2  | an orphan: a DFO-defined class or value list that no other DFO-defined entity points at                                                                                                                                                                                                                       | A value list with no values and no property using it, or a class with no subclasses, instances or property using it. Not necessarily wrong — a class only the pipeline data uses shows up here too — so check whether it is still needed, or link it into the graph. Individuals, values and properties are never checked, because what points at them is the pipeline data, which the compiler does not read.                                                                              |
| A3  | a statement made through a property the DFO mints sits on a node the property's `domainIncludes` covers: the node's `typeOf` target (or Property, for a minted property, which states no `typeOf`) is a class the domain lists, or sits under one through its own `subClassOf` chain                          | Move the statement to the kind of node it belongs on, or add the node's class to the property's domain. The chain is followed only as far as the bench states it, so a domain naming a Data Commons class above a reference will not cover that reference: list the class it is typed to. Thing does not cover a value, because a value's chain reaches Enumeration instead. Reported once per node and property. A reference with no `typeOf` is skipped, since there is nothing to place. |
| A4  | a value stated through a property the DFO mints is one the property's `rangeIncludes` covers: text needs a data type such as `Text` in the range, and a value that points at a node needs that node's `typeOf` target (or Property, for a minted property) to be a class the range lists, or to sit under one | Correct the value, or add the value's class or data type to the property's range. The chain is followed only as far as the bench states it, as in A3. Reported once per node, property and value, except that text values stated through one property on one node share a single finding. A value that is a reference with no `typeOf` is skipped.                                                                                                                                          |
