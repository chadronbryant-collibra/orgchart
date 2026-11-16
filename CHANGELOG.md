# Changelog

## 1.3.0

### Added

- Workday is the default source. When the Workday roster tools are available,
  Claude finds an organization by name, says how many Workday calls a pull will
  take, pages through it, and builds the roster with the new
  `scripts/workday_roster.py`, reporting complete or partial with reasons. It
  sees only what the user's own Workday security allows. Self-service Workday
  (your own line), Sheets, CSVs and pasted lists still work, and BigQuery is
  available to people who already hold People data access. See
  `references/data-sources.md` and `references/workday-roster.md`.

### Changed

- The scope rule changed from "your own line only" to "whatever your Workday
  access allows". Claude never retries with other IDs or another system after
  Workday refuses.

### Also in this release

- Edit flow: add, change, move or remove positions, proposed roles and dotted
  lines in plain words, with a current-vs-planned diff.
- At-a-glance summary page (`--at-a-glance`) and a fix for text overflowing
  cards on team pages.
- Data-driven themes: dark mode, high contrast, soft pastel, corporate blue,
  colour by function, black and white print, and your own brand colours.
- Added a user manual (shipped inside the skill, so plugin and Desktop installs
  get it), a "what would you like to do" menu for bare `/orgchart`, and guidance
  for edits, proposed roles, dotted lines, current vs planned, the at-a-glance
  page and themes in the skill and help.
- Help, the first lines users see and the README state the Workday scope.
- README install steps are labeled by audience, and the plugin README stands
  alone (no links to files outside the plugin).
- Upload safety: `slides_requests.py pagecheck` compares a readback with each
  page file, and `manifest.json` lists the expected element count per page. The
  writer recipe says to check each page and to send cleanup last, only after the
  check passes.
- Help and "what can you do" now explain layouts, statuses, scenarios and
  privacy limits from a new plain-language overview.
- The skill description also triggers on open or planned roles and current vs
  planned views, and excludes single-person lookups.
- Fixed stale size limits in the statuses reference and FAQ (1,000 people, 120
  pages) and a wrong script path in the layouts reference.
- Template copies go to My Drive (`parentId` `root`) instead of landing in the
  template's shared drive.

## 1.2.0

### Added

- Large organizations: one deck now holds up to 1,000 people and 120 pages.
  Big functions get an overview of their sub-leaders, then team pages per
  sub-leader, repeated for large sub-teams.
- `plan` command that splits a roster over those limits into several decks.
- Function lead names on overview cards.
- Location and metadata lines, and a "Contingent" marker with a legend entry,
  on cards.
- `--title` option and page titles taken from the top leader.
- Compact, per-page request files (`--split-dir`), and `verify` that reads the
  Slides connector's raw output (`--summary` shortens the report).
- Guidance to build large decks in stages: overview first, then one function at a time.
- Guidance that self-service Workday covers only your own reporting line.

### Changed

- Workday suffixes such as "(On Leave)" no longer appear in names. "On leave"
  shows only when the roster is built with `--allow-sensitive leave`.
- Card text uses one size per card type on each page.
- "Team continues on page N" is correct when overview pages are inserted.

## 1.1.2

### Fixed

- Show the top leader and a reporting line to each function on the overview
  when there is one top leader.
- Skip the team page for a function that holds only the top leader.
- Show when a manager's team continues on a later page.

## 1.1.1

### Fixed

- Overview cards say "1 position" instead of "1 positions".
- Overview cards sit in the middle of the slide instead of crowding the top.

## 1.1.0

### Changed

- Overview + team pages is out of beta. Team pages now draw reporting lines,
  place each person under their own manager and show an off-page manager as a
  grey context card. Wide and deep teams continue on extra pages with that
  context kept.

## 1.0.1

### Added

- An organization upload zip, `orgchart-plugin-v<version>.zip`, laid out the
  way Claude's "Upload a plugin" expects: `.claude-plugin/plugin.json`,
  `skills/orgchart/`, `README.md` and `CHANGELOG.md`. Owners can add it for
  everyone, and anyone can upload it for themselves under Customize > Plugins.

### Changed

- Friendlier plugin description.
- Claude keeps internal check details (like the receipt's account fields) out of
  its replies and says what it didn't check in plain words.

## 1.0.0

Based on the earlier internal org chart engine v1.6.0, packaged as a
standalone skill.

### Added

- A guided flow: connector check, text preview, layout choice, then an
  editable Google Slides deck.
- A template catalog with a neutral canvas, a Collibra template and synthetic
  roster starters.
- Open, planned and resigned statuses, with size limits and a text outline.
- Install paths for Claude Code and Claude Desktop.
- A Slides request compiler with readback verification.
- Public-content checks and regression tests.

### Changed

- Elbow connectors are the default, card text is smaller, and hierarchy
  subtrees are centered under their parents.
- Local geometry is a preview aid only. It is not proof that a deck was
  created.

### Fixed

- Prevented duplicate names for repeated function panels on larger charts.
- Packed sibling branches onto fewer compact hierarchy pages.
- Put leaders and their reports in separate bands with reporting lines.
- Drew clear dotted matrix links and listed undrawn links in a readable table.

### Known limits

- Departments and teams groups people by function without reporting lines.

