# Data sources

Use only people and fields the user is allowed to see. Confirm source, scope,
as-of date and completeness; do not guess missing managers or fill missing pages.

Scope, stated up front to users: Workday is the default, and it returns only
what the signed-in user's own Workday security allows. Claude never widens that.

Choose the source in this order. Detect each by its tool names, not by the
server or connector name, because those differ between environments.

| Order | Source | Detect by | Who can reach it | Scope |
|---|---|---|---|---|
| 1 | Workday roster tools | `lookup_supervisory_org`, `query_roster`, `discover_roster_scopes` | Anyone the Workday MCP server is enabled for | Any supervisory organization the caller's Workday security can see, one or two levels deep, as of today |
| 2 | Workday self-service tools | Your profile, manager, reporting chain and direct reports tools | Everyone with the Workday connector | The caller's own line, one manager level per call |
| 3 | Google Sheet, CSV, pasted or typed list | The user provides it | Everyone | Whatever the file holds |
| 4 | BigQuery People data | BigQuery query tools, plus the user confirming they hold People data access | People Solutions today | Any organization in the People data mart; history possible |

Rules:
- Workday roster tools: follow [Workday roster](workday-roster.md). Give the
  call-cost advice first, page sequentially, stop on any outcome other than
  `ok`, and run `scripts/workday_roster.py` on the saved pages. Report
  complete or partial with its reasons; never fill gaps by guessing.
- A roster from the Workday roster tools arrives as flat rows with a count-only
  completeness report. Treat a `partial` report as partial: name the
  sub-organizations or levels that are missing, and never present the chart as
  complete. Contingent workers arrive with worker type `contingent` and no
  `[C]` in the name. A head row added with `--add-head` is flagged in the report
  (`head_row_added`, `head_row_synthesized_fields`) because its name and title
  were not read from Workday.
- Self-service tools build only the caller's own line. For a wider chart
  without roster tools, ask for a Sheet or CSV (for example a Workday team or
  supervisory-organization report).
- If Workday refuses a scope or returns nothing, say so and offer a Sheet or
  CSV. Do not retry with other IDs or switch to BigQuery to get around it.
- BigQuery is offered only to users who already have People data access; ask
  for name, title and manager only, active workers, and the as-of date. Never
  suggest it to someone who doesn't.
- Other connectors (for example a directory "who is this person" lookup or an
  Atlassian org tree) don't return reporting lines. Don't build a chart from
  them.

A Google Sheet, CSV, pasted table or typed list can supply `node_id`,
`display_name`, `title`, `manager_node_id`, `function` and `status`. Use stable
IDs for reporting links. A blank manager identifies a root. Optional
`dotted_to_node_ids` contains semicolon-separated secondary links. JSON can use
flat rows or canonical people, positions and relationships. See the synthetic
starters for examples. Keep the current baseline separate from proposed changes.

The normalizer removes only recognized trailing Workday name descriptors,
including repeated suffixes: on leave, leave of absence, contingent worker,
contingent, contractor, terminated, inactive, pending start and retired
(case-insensitive). Other parentheticals are preserved. Contingent descriptors
supply a missing worker type; terminated, inactive and retired supply a missing
resigned status. Explicit worker types and statuses take precedence. Pending
start supplies no additional field.

Leave descriptors are always removed from names. They become "On leave" in
card details only with `--allow-sensitive leave`; otherwise they are discarded.
The count-only receipt records `mapping.descriptors_stripped` and
`mapping.descriptor_leave_dropped`, without names. Location appears first in
card details, followed by metadata; the renderer uses up to two detail lines,
joining extra items on the second line with " · ".

Flat and CSV sources with one root derive a title from the cleaned root name:
"Person Delta 12's organization" (or a trailing apostrophe for names ending in
s). Multiple roots use "Organization chart". Canonical sources retain
`organization.name` when present. `normalize --title` overrides either title.
