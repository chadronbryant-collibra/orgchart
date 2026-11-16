---
name: orgchart
description: "Build or update an editable Google Slides org chart from Workday, a roster, a Google Sheet or a CSV. Use for org charts, team charts, reporting lines, adding, moving or removing positions, planned roles, open roles, dotted lines, current vs planned headcount views, reorg what-ifs, and changing how an org chart looks (dark mode, brand colours, accessible, print). Not for looking up one person's manager, and never for pay, performance or contact details."
metadata:
  version: "1.3.0"
---
# Org chart

Scope, in one line for users: Workday is the default source, and it shows only
what your own Workday access allows. With the Workday roster tools that can be
any organization Workday lets you see; with only the self-service tools it is
your own line (you, your manager, your reporting chain, your direct reports).
For anything else, use a Google Sheet, a CSV or a pasted list. Workday security
decides; never try another route to get around a Workday refusal.

Commands: `/orgchart` starts a chart; `/orgchart templates` lists choices;
`/orgchart update <deck link>` updates a chart; `/orgchart help` explains the flow.

For `/orgchart help`, "what can you do" or any question about what is possible,
read [overview](references/overview.md) and answer from it in plain words. It
points to the full [user manual](references/manual.md). No connector is needed
to explain this, so don't check tools first.

For a bare `/orgchart` with no details, open with this menu, then wait:

> What would you like to do?
> 1. Build a new org chart from Workday, a list, a Sheet or a CSV
> 2. Add, move or remove positions, or add a proposed role
> 3. Add dotted lines for second relationships
> 4. Compare current vs planned
> 5. Change the look (dark mode, brand colours, accessible, print)
> 6. Update a deck I already have (paste the link)
> 7. See what is possible (help)
>
> I pull from Workday by default and see only what your Workday access allows.
> You can also give me a Sheet, a CSV or a pasted list.

If the user names a task, skip the menu.

1. Check which Google Drive and Google Slides tools are available, plus Workday
   (roster tools or self-service tools) and Google Sheets tools, and say what is present or missing in one
   line. Confirm the signed-in account and access. If Drive or Slides is
   missing, walk the user through [connector setup](references/connector-setup.md)
   and offer a text preview meanwhile.
2. Ask for purpose (current, planned or mixed), audience and as-of date. Keep
   proposed positions distinct from current facts.
3. Get people, Workday first, and say up front what the source can reach.
   Follow the order in [data sources](references/data-sources.md):
   - Workday roster tools (`lookup_supervisory_org`, `query_roster`,
     `discover_roster_scopes`), if present: find the organization by name, give
     the call-cost advice, page through sequentially, save each page, then run
     `python3 scripts/workday_roster.py` and report complete or partial. See
     [Workday roster](references/workday-roster.md).
   - Workday self-service tools only: the signed-in user's own line, one
     manager level per call.
   - A Google Sheet, CSV or pasted list with node_id, display_name, title,
     manager_node_id and function columns, for anything Workday can't give.
   - BigQuery, only when its tools are present and the user says they hold
     People data access there.
   Pick by tool name, never by server name. Do not switch sources without the
   user's say-so, and never try another route after Workday refuses. See
   [privacy](references/privacy.md).
   Large organizations: one deck holds up to 1,000 people and 120 pages. Big
   functions get their own overview of sub-leaders, then team pages per
   sub-leader. If a roster is larger, run
   `python3 scripts/org_chart_geometry.py plan <roster>.json` to get a split into
   several decks, and agree the split with the user before building anything.
4. Normalize locally and show the text outline, status totals, recommendation
   and page plan before any Slides call. Resolve missing or ambiguous links.
5. List the [templates](references/templates.md) and choose a template and
   [layout](references/layouts.md). Recommend one with a one-line tradeoff.
   Starter rosters are sample data, not presentation templates.
6. Copy the selected template into the user's My Drive (Drive `copy_file` with
   `parentId` `root`) or the folder they name; without a parent the copy lands
   beside the template, possibly in a shared drive. Compile geometry with `slides_requests.py`, and
   send each page file through Slides one call at a time. Follow the [writer recipe](references/slides-writer.md):
   check every page against a readback, and send `cleanup.json` last, only after the page check passes. If writing is unavailable, return
   the preview and say no deck was created. Reconcile uncertain writes before retry.
7. Offer to update the deck later, compare a scenario or export. See [statuses](references/statuses.md)
   and [model and cost guidance](references/models-and-cost.md).

## What users can ask for

Each item has its own page. Read it only when the user asks.

- Add, change, move or remove a position, propose a role, add or remove a dotted
  line, show current vs planned: [editing](references/editing.md). Confirm
  removals and moves first. Apply edits to a copy; never overwrite the roster.
- A summary page of counts at the front: add `--at-a-glance` to the `layout`
  command. It is off by default; offer it for decks over about 15 people.
- Colours, fonts, dark mode, brand colours, accessibility, print, footer:
  [themes](references/themes.md). Ask for `--theme` or `--theme-file`; show the
  palette before building.
- Statuses, headcount and the legend: [statuses](references/statuses.md).
- Everything in plain words with copy-paste requests: [manual](references/manual.md).

Limits to say plainly: logos and pictures come only from the template; colour by
function has no key on the slide; 8 dotted lines are drawn per deck and the rest
are listed; edits work on the roster, not on a Sheet or Workday directly.

## Build large decks in stages

Do not try to deliver a big deck in one pass. With `--split-dir`, send the overview pages first and show the user a thumbnail, then add one function or one sub-leader's team pages at a time, one `update_presentation` call per page file, checking each page with `pagecheck` and a thumbnail. Send `cleanup.json` last, after `pagecheck` passes for every page. Offer to stop after any stage: a deck with the overview and the functions the user cares about is a good result. Pages are independent, so the user can come back and add the rest later.

## Talk to the user

Many users are not technical. Lead with the outcome, use plain words, and say
what you have not checked. Never include pay, performance, personal contact or
protected details, even when the source has them, and say so if asked. Do not paste commands unless they ask.
The receipt file is for your own checks: don't repeat its field names or
values (such as `account_plane` or source verification) to the user. If the
Google account wasn't checked, just say so in plain words.

## Local preview

Run from the skill folder with Python 3.10 or newer. Any folder works for the
working files; the examples use `./orgchart-work` for brevity. The folder is
created on demand and contains roster data. Workday roster files hold People
rows, so use a folder outside any repository (with absolute paths) and delete it
when the chart is done.

```sh
mkdir -p ./orgchart-work
python3 scripts/normalize_org_chart.py normalize examples/starters/simple-team.json --output ./orgchart-work/render.json --receipt ./orgchart-work/receipt.json
python3 scripts/preview_org_chart.py outline ./orgchart-work/render.json
python3 scripts/templates.py list
python3 scripts/org_chart_geometry.py layout ./orgchart-work/render.json --mode compact_hierarchy --output ./orgchart-work/geometry.json   # add --at-a-glance for a summary page
python3 scripts/org_chart_geometry.py validate ./orgchart-work/geometry.json
python3 scripts/slides_requests.py compile ./orgchart-work/geometry.json --theme collibra-2026 --layout-id g3efe399732d_0_346 --output ./orgchart-work/requests.json
```

The normalizer refuses to overwrite outputs; choose fresh names for another run.
The helpers are local and do not create a deck. For scenario edits use
`scripts/apply_org_chart_scenario.py --help` and preserve the original baseline.
