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
| 11 | Selectable visual themes for cards and slides, drawn from the Collibra brand toolkit (colour sets, card styles, fonts) | Chadron's request 2026-11-12. Design with Codex CLI after this release: put every card colour, border and font behind one theme table in the geometry/compiler, keep the current look as the default theme, and gate extra themes behind an optional `--theme` choice. Check each theme with `collibra-design` and thumbnails. |

## Live canary (synthetic, 2026-11-12)

A 150-person synthetic roster (four functions of 70, 35, 25 and 19 people)
was laid out in enterprise overview mode, compiled with `--split-dir`, and
delivered to a copy of the Collibra template in My Drive
(`Org chart canary 1.2 drilldown (synthetic)`).

- Layout: 23 pages. Top overview, a sub-leader overview for each function that
  needed one, a team page per sub-leader, and plain pages for the 19-person
  function.
- Request sizes: 413 total requests for the delivered pages (54, 73 and 118 per
  page). Full-deck page files range from 8.7 KB to 34 KB, 588 KB in all
  (2,098 requests including 59 template-slide deletions).
- Delivered pages: the top overview, the Engineering sub-leader overview and
  one team page with a "Team continues on page N" marker and a contingent
  card. Each went through one `update_presentation` call, then `cleanup.json`
  (59 template slides) in a fourth call. All calls succeeded first time.
  I did not send the other 20 pages, because each full-size page costs about
  12,000 output tokens to relay by hand through the connector.
- `verify --summary` on the raw `read_presentation` output
  (`{"content": {"slides": [...]}}`, read with the exact `fields` mask) for the
  delivered pages: `PASS 48 FAIL 0`.
- Thumbnails checked: top overview, sub-leader overview and the team page
  showed no overlaps, clipped text or missing lines. The contingent card and
  its legend entry rendered with the dash-dot border.
- Delivery time: not stopwatch-measured. Connector calls returned within a
  few seconds each; wall-clock is dominated by the model writing the request
  arrays, which scales with bytes.

Defects found by the canary and fixed in this branch:
1. Stray single-card "overview · continued" pages between sub-leader team pages.
2. "Team continues on page N" printed on grey context cards and on overview
   cards, pointing at arbitrary pages.
3. Sub-leader cards showed "Lead: <own name>".
4. A sub-leader overview with more than six leaders wrapped to a second row
   whose reporting lines could not be drawn. It now holds up to eight leaders
   in one row and continues on a further page after that.

Not fixed (polish, low risk): each function with sub-leaders still gets a page
holding only the function head plus a grey context card of their manager
(`Engineering`, `Finance`, `Operations` pages in the canary). It exists so
every person has one real card; folding the head onto the overview would
remove it but changes the "every person appears once" rule.

Ceiling check. Slides itself is not the limit: pages are independent, and the
per-page request counts stay near 120. The limit is delivery cost. Full-size
pages are about 34 KB (roughly 12,000 output tokens) each, so 82 pages (800
people) would be around 1M output tokens and a 120-page deck more. I did not
build one. Recommendation: keep 1,000 people and 120 pages as hard ceilings,
but have the skill warn above about 25 pages and offer `plan` to split by
function. Compiler compaction (one z-order request per page, default line and
outline properties dropped) cut the largest page of a 150-person roster by
about 10% (55,097 to 49,730 bytes, 190 to 172 requests) and the 23-page canary
to about 531 KB. Lossless trimming stops there: each card still needs six
requests because Slides has no style-by-reference. Only 5 of 23 canary pages were hand-delivered (about 25K
tokens per large page), which is why the remaining 18 were left undelivered.
Decision (Chadron, 2026-11-12): do not add a delivery client. Real users build
over time, so the skill guides a staged build through the connector instead.
The canary is a proof of concept; 6 of 23 pages delivered is enough.

## Open items for the joint review

- Decide the soft page warning (about 25 pages) described above.
- "On leave" stays hidden unless `--allow-sensitive leave`, and the version is
  1.2.0 (minor), as proposed; both are drafted here pending Chadron's say.
- Delivering the remaining 20 canary pages is optional; it would only repeat the
  per-page pattern already verified.
