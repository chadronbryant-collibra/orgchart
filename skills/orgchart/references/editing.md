# Editing an org chart: add, change, move, remove, propose

This is how to change a chart you already have, in plain words. Your original
roster is never overwritten: every edit writes a new "planned" file next to it,
so the current view is always one command away.

## For the model

1. Make sure you have the normalized roster JSON (`normalize_org_chart.py normalize`
   on the user's CSV, flat JSON or Sheet export). Keep it as the baseline.
2. Turn what the user asked for into a short edit list (CSV or JSON, columns
   below). Look up IDs from the roster; never guess an ID.
3. **Confirm before applying** (see "What Claude confirms first").
4. Run the edit, then show the diff:

```bash
python3 scripts/apply_org_chart_scenario.py edit roster.json edits.csv --output planned.json
python3 scripts/preview_org_chart.py diff roster.json planned.json
```

5. Read the one-line summary back to the user in their words, for example
   "1 added (1 proposed), 1 moved, 1 removed, dotted lines 1 -> 2; headcount 7 -> 7".
6. Build the slides from `planned.json` the usual way. Changed positions carry a
   status and a short annotation on the card (for example "Proposed: assumes
   budget approval"). To show current and planned together, build one deck from
   each file, or put the diff text on a notes page.

The older `apply_org_chart_scenario.py scenario.json --output ... --receipt ...`
route still works for hand-written scenarios. Use `edit` for everything a user
asks for in conversation.

## Edit list columns

`op, node_id, display_name, title, manager_node_id, function, status, note, dotted_to_node_ids, reports, reassign_to_node_id`

| op | What it does | Needs |
|---|---|---|
| `add` | New position (planned or open if no name is given) | `node_id` (new), `title`, `manager_node_id`; name for a filled role |
| `modify` | Change name, title, function, status or note | `node_id` and at least one change |
| `move` | Change who a position reports to | `node_id`, `manager_node_id` |
| `remove` | Take a position out | `node_id`; see below if it has reports |
| `propose` | Mark an existing position as planned (proposed) | `node_id`; `note` is the assumption |
| `open` | Mark a position as an open role (person leaves, role stays) | `node_id` |
| `dotted_add` | Add dotted-line links from a position | `node_id`, `dotted_to_node_ids` (separate with `;`) |
| `dotted_remove` | Remove a dotted-line link | `node_id`, `dotted_to_node_ids` |

Statuses: filled, open, planned, resigned, other (other needs a label in `note`).
Headcount: filled +1, open 0, planned 0, resigned -1, other 0.

JSON works too: a list of the same objects, or `{"edits": [...]}`.
Examples to copy are in `examples/edits/`.

## Removing someone who has reports

The edit stops with a plain message that names the people affected. The user
then picks one:

- **Reassign**: `reports=reassign` and `reassign_to_node_id=<new manager>` (or
  `reports=reassign:<id>`). The reports move up or across and are marked moved.
- **Cascade**: `reports=cascade` removes the person and everyone below them.
- **Stop**: change nothing. Leaving `reports` blank also stops.

Never choose for the user.

## Dotted lines

- Both people must exist, a person cannot link to themselves, and a pair can
  only have one line (A to B and B to A count as the same line).
- A deck draws up to **8** dotted lines. Extra links are kept in a companion
  list (`companion_links` in the planned file) and the summary says how many were
  drawn and how many were listed, for example "8 drawn on the chart, 3 listed in
  a companion table". Offer to put the list in a table on a notes or appendix page.

## What Claude confirms first

Say back the plan in one or two lines and wait for a yes when any of these apply:

- A removal (and which choice for any reports).
- A move that changes a manager's team size by more than a few people.
- A proposed role with no assumption stated: ask for one short reason, or offer
  the default ("assumption not yet confirmed").
- More than about ten edits in one go.
- A name or title that matches more than one position.

## Undo

The baseline roster is never changed and the output file must be new. To undo,
open the original roster again, or delete `planned.json` and re-run with a
shorter edit list. To drop one change, remove its row and run again.

## Cheat sheet: things you can say

- "Add a planned Director of Analytics under the VP of Product, assuming budget is approved next cycle."
- "Move Person Gamma to report to Person Delta."
- "Remove the open Product Operations Lead role."
- "Remove Person Delta and move their team to Person Beta." (reassign)
- "Mark Person Epsilon's role as open, backfill expected next quarter."
- "Mark the Customer Advisor role as proposed."
- "Change the title of Person Epsilon to Senior Director."
- "Add a dotted line from Person Gamma to Person Eta."
- "Remove the dotted line between Person Beta and Person Delta."
- "Show current vs planned." (runs the diff and reads back the summary)

## Limits

- Edits work on a normalized roster, not directly on a Google Sheet or Workday.
- One reporting manager per position; dotted lines are for secondary relationships.
- 8 dotted lines are drawn per deck; the rest go to a companion list.
- The planned file shows removed positions only in the diff, not on the chart.
- Annotations should stay short (a phrase). Long notes are kept in the file but
  may crowd the card.
- Use only roster data the user is allowed to see. Examples here are synthetic.
- Edits do not publish anything; building or updating slides is a separate step.

## When something fails

Every failure is a plain sentence naming the person or step, for example
"Edit 2: I could not find 'demo-999' in the roster." or "removing Person Beta
(VP Product Examples) would leave 2 people without a manager: ...". Nothing is
written when an edit fails. Fix the row and run again.
