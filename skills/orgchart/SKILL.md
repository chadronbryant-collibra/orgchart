---
name: collibra-org-charts
description: Create and revise editable current, planned or mixed org charts from authorized rosters, with five layout families, legends, insights, drilldowns and native attached connectors.
metadata:
  version: "1.6.0"
---

# Collibra org charts

Apply by default for org-chart creation or structural revisions. Before
brand-dependent work follow `../../references/brand-refresh.md`, including its
60-day source review check. Read `../../references/org-charts.md` for layout
routing, data/relationship semantics, add-ons and native acceptance. Apply the
shared `collibra-design` and slide contracts. A prose-only edit does not need a
roster read or a new chart.

1. Establish current, planning or mixed, scope, audience and as-of date. Offer
   an authorized people source or supplied CSV/JSON/paste. Keep unknowns unknown
   and separate baseline facts from proposals.
2. Inspect the available native writer and a template the user may use. Copy
   the template. No template asset or live connector is bundled here.
3. Apply scenario changes when requested, normalize, then recommend and plan
   geometry using the bundled dependency-free helpers. Use `--help` for schemas
   and options. Do not hand-build a payload to bypass validation.
4. Choose compact hierarchy, leadership bands, functional columns, matrix, or
   enterprise overview plus drilldowns. Recommend one and explain its tradeoff.
   Add enrichment, legends, insights or comparison pages only when useful.
5. Render native editable cards and attached connectors through the available
   writer. Preserve template safe areas, semantic type and stable names. Read
   back native endpoints and reconcile cards, relationships and totals.
6. Inspect all slides at native scale and test move/restore on a disposable
   card before an attachment claim. Keep offline validation, native behavior
   and human acceptance distinct. Without a writer return the validated model,
   geometry and binding plan as `STOPPED_NO_DECK_WRITER`.

## Local helpers

Python 3.10+, standard library only. Paths below are relative to this skill:

```sh
python3 scripts/normalize_org_chart.py normalize examples/synthetic-roster.csv --output /tmp/org-render.json --receipt /tmp/org-receipt.json
python3 scripts/org_chart_geometry.py recommend /tmp/org-render.json
python3 scripts/org_chart_geometry.py layout /tmp/org-render.json --mode compact_hierarchy --output /tmp/org-geometry.json
python3 scripts/org_chart_geometry.py validate /tmp/org-geometry.json
```

Use `scripts/apply_org_chart_scenario.py` for scenario edits and
`scripts/bind_pptx_connectors.py` for a rendered PPTX binding manifest. Inputs
and outputs can contain people data; use authorized local destinations. These
helpers read/write supplied local files. They make no network, connector,
model or subprocess call and do not create a presentation by themselves.
Connected acquisition requires the active deployment's verified caller/scope
controls. Never treat a requested manager ID as access authorization.
