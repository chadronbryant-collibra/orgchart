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
