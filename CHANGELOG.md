# Changelog

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
- `deliver_slides.py`: optional direct delivery of a `--split-dir` compile to the
  Slides API (resumable, reorders pages, cleanup last, no replay of failed writes).
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

