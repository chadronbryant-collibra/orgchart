# Release candidate notes (next release after 1.1.2)

Status: held for joint review. No version bump, tag, release, Drive upload or
Confluence change is part of this branch. Versions and CHANGELOG are untouched.
All fixtures are synthetic.

## Gaps from the 1.1.2 live tests, now fixed

| # | Gap | Fix |
|---|---|---|
| 1 | Workday suffixes such as "(On Leave)" ended up in names | Only a whitelist of known descriptors is stripped (on leave, contingent worker, contractor, terminated, inactive, pending start, retired); other parentheticals such as a nickname stay. Contingent maps to the contingent worker type, terminated and similar to resigned when no status was given. "On leave" shows on the card only with `--allow-sensitive leave`; otherwise it is dropped and counted in the receipt (no names). |
| 2 | Location and metadata never rendered | Up to two detail lines render under the title. |
| 3 | Contingent workers had no marker | A "Contingent" text line on the card and a legend item with its own border pattern. |
| 4 | Overview cards omitted the function lead | A "Lead:" line (several heads show "+N more", an open head shows "Open role"), including rosters with no single root. |
| 5 | Generic page title | Title comes from the single root ("Person X's organization"), and `normalize --title` overrides it. |
| 6 | Card font varied by title length | One name size and one body size per card type per page, from the tightest card, with the 8 pt floor kept. |
| 7 | Heavy delivery | Compiled JSON is compact (about 54% smaller on a 12-person, 4-page synthetic deck), `--split-dir` writes one request file per page plus a last-step `cleanup.json`, and `verify` accepts the raw connector readback (`{"content": {"slides": [...]}}`, a JSON string, or MCP text blocks), merges several readbacks, and has `--summary`. |
| 8 | Data sourcing unclear | SKILL.md step 3 says self-service Workday covers only your own line and asks for a Sheet or CSV export for wider orgs. |

## Large organizations

Limits are now module constants: 1,000 people and 120 pages per deck (were 200
and 30), enforced together in the normalizer, layout and validation.

Design:
1. Top overview: one card per function with its lead. More than 12 functions
   continue on further overview pages.
2. If a function needs more than two team pages or has more than 40 people, it
   gets its own overview of sub-leaders (headcount per subtree), then team
   pages per sub-leader. A sub-leader whose subtree is still large repeats the
   step one level down (depth limit 4).
3. "Team continues on page N" is resolved after all pages exist, so it is
   right with inserted overview pages. The geometry result carries a
   `navigation` list (page, title, level, parent page).
4. Above the ceiling, `org_chart_geometry.py plan` proposes several decks by
   whole subtrees (an overview part plus parts that each lay out validly) and
   can write one input file per part. It never creates decks.

Tested with synthetic rosters: 300 people lay out in 30 pages, 800 in 82, and
1,200 is refused by `layout` and split by `plan` with every person covered
exactly once.

Checks run: unit tests (69), public-content check, template manifest, desktop
and plugin zip builds.

## Other improvement options, ranked

| Rank | Option | Recommendation |
|---|---|---|
| 1 | Roster route for average employees (Workato-hosted Workday roster tool) | Highest value. Only a wider roster source removes the Sheet/CSV step. Track in the separate Workday MCP work; this skill already accepts its output through the flat or canonical formats. Build after that route exists. |
| 2 | Live render-and-look check in the skill flow (thumbnail per page with a fixed checklist) | Do next. Cheap and caught the issues behind gaps 5 and 6. |
| 3 | Page index / table of contents slide for decks above about 10 pages, with links to pages | Do with the large-org release. The `navigation` data is ready. |
| 4 | Update an existing deck from a new roster (diff and patch instead of rebuild) | Valuable but larger; plan separately. Stable object IDs already make it feasible. |
| 5 | Scenario compare (current vs proposed with headcount deltas) | Medium. Statuses and the scenario script exist; add one summary slide. |
| 6 | Export to PDF or PNG for Slack and email | Low effort through Drive export; add as an optional last step. |
| 7 | Accessibility: alt text per page and a check that colour is never the only status signal | Do soon; small. |
| 8 | Skill version check and a "how did it go" feedback link | Small; add once the release channel is settled. |
| 9 | CSV import helper for Workday report column names | Small, removes mapping questions. |
| 10 | Search by name to build a team from several people | Needs a directory source with reporting lines; defer. |

## Open items for the joint review

- Confirm the 1,000-person and 120-page ceilings against what Slides handles in a
  live deck (not tested live here; local geometry and compile only).
- Confirm "On leave" handling under the privacy rules (hidden unless the user opts in).
- Decide the version number (feature release, so minor) and the CHANGELOG text.
- Run one live Slides canary for a drilldown deck and one for `--split-dir` delivery.
