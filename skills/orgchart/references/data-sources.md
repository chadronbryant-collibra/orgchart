# Data sources

Use only people and fields the user is allowed to see. Confirm source, scope,
as-of date and completeness; do not guess missing managers or fill missing pages.

Workday self-scoped tools may provide your profile, manager, reporting chain and
direct reports. Use only the signed-in user's own line, with one manager level
per call. Check each available tool's actual scope; do not treat an identifier
or the connector's account access as authorization for a wider roster.

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
