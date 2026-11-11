# Statuses and limits

Use `filled`, `open`, `planned`, `resigned`, or `other`. For `other`, supply a
nonempty `statusLabel` (CSV also accepts `status_label`). An omitted status
defaults to filled. Headcount impact is +1 for filled, 0 for open and planned,
-1 for resigned, and 0 for other. These are position-level planning impacts;
confirm the intended baseline before presenting a net change.

The chart accepts up to 200 people or positions, 30 pages and 8 matrix links.
Split a larger roster or use a separate relationship list. Do not silently
omit records to fit.
