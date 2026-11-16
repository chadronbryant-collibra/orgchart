# Workday roster tools

The Workday roster tools are read only and run as the signed-in user. Workday
security decides which rows come back. Treat any field a response leaves out as
unknown. Pulled rows are People data: save pages outside the repository and
keep the files local.

## The three tools

| Tool | Input | Use |
| --- | --- | --- |
| `discover_roster_scopes` | `anchor`: `orgs_i_manage`, `self` or `my_manager` | Find the user's own, manager's or managed orgs |
| `lookup_supervisory_org` | `name`, 3 or more characters | Find org ids by part of a name; reference data, not access |
| `query_roster` | `scope_id`, `depth` 1 or 2, `unit`, `offset`, `page_size` up to 100, `as_of_date` (today only) | One org page per call |

Unit 0 is the scope org. Units 1 to N are its direct sub-orgs (depth 2).
Inactive sub-orgs are included and marked `unit_status` `inactive`.

## Response shape

The response arrives under a `result` key. Every value is a string. Fields:
`outcome`, `completeness` (`complete` or `partial`), `reason_codes` (a comma
separated string such as `more_pages,depth_limit`), `has_more` (`'true'` or
`'false'`), `unit`, `unit_label`, `unit_status`, `sub_org_count`,
`total_in_unit`, `returned_count`, `next_unit`, `next_offset`, `applied_depth`
and `rows`. The first page's `sub_org_count` and `total_in_unit` give a cost
estimate before you pull more.

Row fields: `node_id`, `display_name`, `title`, `manager_node_id`, `function`,
`status`, `worker_type`, `node_type`, `location`. Some responses mark
contingent workers as `employee` with a trailing `[C]` on the name; the assembler
removes the mark and sets `contingent`. Others arrive with worker type
`contingent` and no `[C]`; the assembler keeps that as it is. `function` is the org label with the unit head's name in
parentheses (`--clean-function` drops it). Open positions are not returned.

The head of the scope org is not a row. Top-level rows point at a manager who
is absent, so the assembler reports those links as dangling. In sub-org units
the manager is a unit 0 row, so links resolve across units.

## Outcomes

| Value | Meaning |
| --- | --- |
| `ok` | Page returned |
| `invalid_scope_id` | The id is not a 32-character org id; look it up again |
| raw "Tool execution failed" | A well-formed id that does not exist or that Workday refuses. There is no typed outcome. Stop and ask for another org |
| `depth_limit` | Reason code: sub-orgs below depth 2 are not included |
| `row_cap_reached` | A unit reached 5,000 rows; narrow the scope |
| `unsupported_effective_date` | Only today is supported |
| `rate_limited`, `source_unavailable`, `snapshot_changed` | Stop and say so; retry only if the user asks |

`visibility_limited` as a reason code means some people are hidden from the
user. Hidden managers show up as blank or missing links.

## Cost

A page on unit 0 costs 3 Workday calls. A page on a sub-org unit costs 5. A
call takes about half a second. Depth 1 is about `ceil(people / 100)` pages.
Depth 2 is at least `1 + sub-orgs` pages, because each sub-org is its own unit
even when it is small or inactive and empty.

| Pages | What to do |
| --- | --- |
| 5 or fewer | Just pull |
| 6 to 20 | Tell the user the page count and time first |
| More than 20 | Get an explicit yes first; offer a narrower org or depth 1 |

Rows pass through the conversation on their way to files, so a pull of several
hundred rows also costs tokens. Say so.

```sh
python3 "$SK/scripts/workday_roster.py" plan --people 300 --sub-orgs 13 --depth 2
```

prints a lower-bound estimate (`--people` is a rough headcount, 0 if unknown).

## Pull, assemble, normalize

1. Call `query_roster` for unit 0 at offset 0. Then repeat with `next_unit` and
   `next_offset` while `has_more` is `'true'`. Go one page at a time. Do not
   retry in a loop; on a failure, stop and report it.
2. Save each response unedited to its own file in a temporary folder outside the
   repository: `page-001.json`, `page-002.json` and so on. Always save the
   digest fields (`rows_digest` and `rows_digest_alg`) with each page. Copy
   every row exactly, never tidy or shorten values, and never merge pages by
   hand. The assembler warns when a page has no digest, because a changed
   location or similar value cannot be detected without it.
3. Assemble (`SK` is the skill folder, `W` the working folder):

```sh
python3 "$SK/scripts/workday_roster.py" assemble "$W"/page-*.json \
  --output "$W/roster.json" --report "$W/report.json"
```

4. Hand off to the normalizer:

```sh
python3 "$SK/scripts/normalize_org_chart.py" normalize "$W/roster.json" \
  --output "$W/render.json" --receipt "$W/receipt.json"
```

The assembler merges pages, removes duplicate rows, checks manager links and
cycles, and checks that the page chain has no gap. It never overwrites the
roster file. The count-only report is rewritten on each run, so a stopped run
can be repeated with new flags. Its `verdict` is `complete` or `partial`; quote
`partial_reasons` in plain words. It also gives `size_advice`: `single_chart`,
`staged` (above 200 people) or `split_decks` (above 1,000).

Flags:

- `--dangling roots` makes rows whose manager is outside the pull into roots.
  Use it only after the user agrees.
- `--add-head "Name" --head-title "Title"` adds the one missing org head as a
  row, with the org's function label. The title defaults to "Organization head".
  It refuses unless exactly one manager is missing.
- `--clean-function` drops the trailing manager name from function labels.
- `--as-of YYYY-MM-DD` sets `source_as_of` (default today).

A manager cycle stops the run and no roster is written.

The assembler also checks each page's row count against its own
`returned_count`, each unit's rows against `total_in_unit`, that one unit has one
function label, and each page's `rows_digest`. If `integrity` in the report is
not all zero, the run stops: re-save the affected pages from the tool responses
and rerun (`--accept-integrity` writes the roster anyway; use it only after the
user agrees). A page saved without a digest gives a warning, not a failure.

Reading the report:

- Treat `partial` as partial. Say which sub-organizations or levels are missing
  (for example `depth_limit` means organizations below the second level are not
  included) and never present the roster as complete.
  The report's `reason_codes` count pages, not organizations. To name the
  depth-limited organizations, read `unit_label` from the saved pages that carry
  `depth_limit`.
- Contingent workers arrive with worker type `contingent` and no `[C]`.
- A head added with `--add-head` was not read from Workday. Its name comes from
  the org label or the user, and its title defaults to "Organization head" (or
  `--head-title`). The report flags it with `head_row_added` and
  `head_row_synthesized_fields`; tell the user.

## Output fields

The roster has the 15 flat fields the normalizer reads: `node_id`,
`display_name`, `title`, `manager_node_id`, `node_type`, `status`,
`worker_type`, `function`, `location`, `metadata`, `dotted_to_node_ids`,
`markers`, `sort_order`, `source_as_of` and `source_ref`. The tools supply the
first nine. The assembler leaves `metadata`, `dotted_to_node_ids`, `markers` and
`source_ref` blank, numbers `sort_order` in pull order and sets `source_as_of`.
`status` defaults to `filled` and `node_type` to `person`. A blank
`manager_node_id` is a root.
