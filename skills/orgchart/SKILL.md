---
name: orgchart
description: "Build or update an editable Google Slides org chart from a roster, your Workday reporting line, a Google Sheet or a CSV. Use for org charts, team charts, reporting lines, reorg or headcount planning views."
metadata:
  version: "1.0.0"
---
# Org chart

Commands: `/orgchart` starts a chart; `/orgchart templates` lists choices;
`/orgchart update <deck link>` updates a chart; `/orgchart help` explains the flow.

1. Check which Google Drive and Google Slides tools are available, plus optional
   Workday and Google Sheets tools, and say what is present or missing in one
   line. Confirm the signed-in account and access. If Drive or Slides is
   missing, walk the user through [connector setup](references/connector-setup.md)
   and offer a text preview meanwhile.
2. Ask for purpose (current, planned or mixed), audience and as-of date. Keep
   proposed positions distinct from current facts.
3. Get people from a permitted source: Workday self-scoped tools, a Google Sheet,
   CSV, pasted roster or typed list. Workday tools cover your profile, manager,
   reporting chain and direct reports; access is limited to your own line and
   one manager level per call. Do not infer wider access. See
   [data sources](references/data-sources.md) and [privacy](references/privacy.md).
4. Normalize locally and show the text outline, status totals, recommendation
   and page plan before any Slides call. Resolve missing or ambiguous links.
5. List the [templates](references/templates.md) and choose a template and
   [layout](references/layouts.md). Recommend one with a one-line tradeoff.
   Starter rosters are sample data, not presentation templates.
6. Copy the selected template, compile geometry with `slides_requests.py`, and
   send each request chunk through Slides. Follow the [writer recipe](references/slides-writer.md)
   for readback, verification and visual checks. If writing is unavailable, return
   the preview and say no deck was created. Reconcile uncertain writes before retry.
7. Offer to update the deck later, compare a scenario or export. See [statuses](references/statuses.md)
   and [model and cost guidance](references/models-and-cost.md).

## Talk to the user

Many users are not technical. Lead with the outcome, use plain words, and say
what you have not checked. Do not paste commands unless they ask.

## Local preview

Run from the skill folder with Python 3.10 or newer. The working folder is
created on demand and contains roster data; remove it when done.

```sh
mkdir -p ./orgchart-work
python3 scripts/normalize_org_chart.py normalize examples/starters/simple-team.json --output ./orgchart-work/render.json --receipt ./orgchart-work/receipt.json
python3 scripts/preview_org_chart.py outline ./orgchart-work/render.json
python3 scripts/templates.py list
python3 scripts/org_chart_geometry.py layout ./orgchart-work/render.json --mode compact_hierarchy --output ./orgchart-work/geometry.json
python3 scripts/org_chart_geometry.py validate ./orgchart-work/geometry.json
python3 scripts/slides_requests.py compile ./orgchart-work/geometry.json --theme collibra-2026 --layout-id g3efe399732d_0_346 --output ./orgchart-work/requests.json
```

The normalizer refuses to overwrite outputs; choose fresh names for another run.
The helpers are local and do not create a deck. For scenario edits use
`scripts/apply_org_chart_scenario.py --help` and preserve the original baseline.
