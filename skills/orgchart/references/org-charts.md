# Org chart capability guide

## Choose by the reader's question

| Family | Best use | Typical planning range, not a capacity guarantee |
| --- | --- | --- |
| Compact hierarchy | One leader and a readable team map | 6–26 positions, usually 3–6 branches |
| Leadership bands | Executive or onboarding view of leaders | 4–14 leaders; excludes detailed contributor rosters |
| Functional columns | Uneven branch depths across functions | 12–40 positions in 4–6 functions |
| Matrix relationships | Direct hierarchy with a few secondary relationships | 6–24 positions; use a companion table beyond eight secondary links |
| Enterprise overview + drilldowns | Navigate a large organization by section | Roughly 35–500 across pages; overview is not the complete reference map |

The planner supports `compact_hierarchy`, `leadership_bands`,
`functional_columns`, `matrix_relationships`, and `enterprise_overview`.
A family's range describes a use case. Exact canvas, labels, hierarchy depth,
metadata, native writer and app limits determine fit. Never offer 500 positions
as one readable slide or assume a managed app accepts that request.

## Independent choices

- Scenario: current, planning or mixed current-plus-proposed.
- Detail: simple names/titles; enriched approved metadata; reference plus sections.
- Density and canvas: preserve the selected template's safe areas and readable
  type. Split or change the layout when it fails; do not use autofit as repair.
- Cards: filled, open and planned positions; explicitly supplied contractor
  status; optional location, tenure and level.
- People signals: critical role versus critical person, succession,
  promotion recommendation and compensation signals require explicit source
  values and audience authorization. Never infer them from title or tenure.
- Relationships: solid direct reporting; labeled dotted matrix or advisory.
  Multiple meanings need distinct labels. Cross-page links need a table/key.
- Add-ons: compact legend, three to six reconciled insights, function sections,
  leadership context, current/proposed comparison and a separate change ledger.
  Include only what answers the reader's question.

## Model and scenario

Keep `people[]`, `positions[]` and `relationships[]` distinct. A vacancy is a
position without a person. Use stable IDs, never names alone as relationship
keys. Canonical person fields include `personId`, `displayName`; positions use
`positionId`, nullable `personId`, `title`, `function`, `status`, optional
`location`, `workerType`, `level`, `tenureYears`, `compaRatio`, `markers`, `notes`.
Relationships use `fromPositionId`, `toPositionId`, `type` and optional `label`.
Organization metadata records name, scope, as-of date and source label.

The flat CSV/JSON import uses `node_id`, `display_name`, `title`,
`manager_node_id`, optional `function`, `node_type`, metadata and dotted links.
The normalizer emits a layout projection with one `people[]` node per position.
This projection does not replace the canonical source model.

The scenario ledger supports add/remove/move positions, manager changes,
attribute changes, annotations and direct/matrix/advisory relationship edits.
Use the supplied synthetic scenario as the exact input example. Keep the
baseline and the change ledger; proposed changes never write back to the HRIS.
Reject duplicate IDs, missing endpoints, cycles, self-links and ambiguous
managers. Preserve explicit roots and unknown values. Reject incomplete
pagination before calling a connected roster complete.

## Native authoring and acceptance

Use an authorized, inspected native template and create a copy. In an internal
branded deployment use its approved template profile; public users supply a
template they may use. This package contains no retained template assets.
Use the shared slide type, safe-area and geometry contracts. The portable
planner gives starting coordinates; actual template chrome and text measurement
can require repagination. Never flatten cards or relationship lines into an image.

Give each card and connector the planner's stable name. Route behind cards,
keep peers aligned and prevent labels, cards and connector paths overlapping.
Create one attached native connector per rearrangeable relationship. A bus
made from visual segments does not satisfy attachment.

For rectangular Google Slides endpoints use actual connection sites:
`top=0`, `left=1`, `bottom=2`, `right=3`. Prefer attached `STRAIGHT` lines.
Use `BENT` routing only after a canary on the exact native deck. Read back
object IDs, site indexes and actual coordinates; a matching index alone does
not prove the right side. Move and restore a disposable card and verify the
line follows it. PPTX binding is separate evidence from native Slides behavior.
For PPTX use `bind_pptx_connectors.py --help` and the planner's binding manifest;
its validator checks the resulting slide-local OOXML endpoint references.

Reconcile every position once in the primary hierarchy. Repeated drilldown
leaders are labeled context and excluded from totals. Legends include only
used meanings, with labels or patterns in addition to color. Insights use the
same normalized snapshot, scope/date and known-value denominator. Render and
inspect every final slide at native size and check overflow and completeness.
If a native writer is unavailable, return validated data, geometry and a
binding plan labeled `STOPPED_NO_DECK_WRITER`.

## Conversational workflow

Start with current, planned or mixed and the team in scope. Accept an authorized
source, upload, CSV/JSON, pasted roster or user-created planning positions.
Recommend one layout with up to two alternatives. Do useful normalization while
waiting for optional preferences; ask only about consequential missing facts.
Support “add a planned role,” “move this team,” “change the manager,” and
“show current versus proposed.” Recompute layout, pagination, legends and
insights after structural changes. Do not add a cover or appendix by default.

For a recipient without the skill, prepare a self-contained roster request:
ask for Name, Role, Reports to, Team and Status, source scope/date and known
missing fields. Explain that proposed edits stay separate and that an approved
export or pasted roster is supported. Do not claim an unavailable connector.

## Connected enterprise lane

Workato/Airo or another approved adapter can supply an authorized roster and
expose preview/create/status operations to a chat client. The deployment owns
caller identity, scope and field authorization, pagination, freshness,
revocation, retention and delivery permissions. A user-supplied email or manager
ID is not authentication. An integration account's access is not the caller's.
A self-profile/direct-reports capability does not establish arbitrary-team access.

Use one roster read per explicit refresh. Carry source/effective/retrieval dates,
scope, completeness and a content-free correlation reference. Review the scenario
before creation. Bind create to the user, destination, accepted preview revision
and idempotency key. Reconcile uncertain writes through a status operation.
Do not embed credentials or anonymously expose a renderer. Read-only HRIS
acquisition and local scenario editing are the default; live HRIS writes require
a separate authorized workflow.

Public code provides no preconfigured enterprise connection, deployment or
access entitlement. The same planner and data contract serve connected and
portable workflows.

## Adapter-specific options

A managed app may offer starter structures, source/depth prompt choices, saved
drafts/history, source-supplied appendix sections, selected/custom insights,
resigned/Other status labels and a larger canvas or density choices. Query its
capability response before offering those options. The portable helpers above
do not imply those app features. Keep source-supplied appendix content intact
and audience-approved; do not infer individual succession assignments.

Treat density, canvas, full reference/sections and layout as separate choices.
The current writer must validate each combination before creation. If it cannot
fit a full map, show that boundary and offer readable sections without silently
omitting positions. Destination, draft persistence and access checks belong to
the adapter; nothing on the public gallery stores a roster or creates a deck.
