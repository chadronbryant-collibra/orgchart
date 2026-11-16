# Statuses and limits

Use `filled`, `open`, `planned`, `resigned`, or `other`. For `other`, supply a
nonempty `statusLabel` (CSV also accepts `status_label`). An omitted status
defaults to filled. Headcount impact is +1 for filled, 0 for open and planned,
-1 for resigned, and 0 for other. These are position-level planning impacts;
confirm the intended baseline before presenting a net change.

One deck accepts up to 1,000 people or positions, 120 pages and 8 matrix links.
Split a larger roster (see `plan` in layouts) or use a separate relationship list. Do not silently
omit records to fit.

Contingent workers (`kind="contractor"` or `worker_type="contingent"`) have a
visible "Contingent" text marker and a page legend item with the other palette
fill and a long dash-dot border. Filled contingent cards use that border and
fill too. Position statuses remain independent: an open contingent role shows
both "Open role" and "Contingent" and keeps the open-role border.

## Legend and proposed roles

Each page has a legend that shows only the statuses used on that page, with
text and a line pattern as well as colour. A proposed role is a planned card
with a short note ("Proposed: assumes budget approval"). The at-a-glance page
has its own one-line key instead of the legend chips. Ask for it with
`--at-a-glance`. See [editing](editing.md) and the [manual](manual.md).
