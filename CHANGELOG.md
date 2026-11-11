# Changelog

## 1.1.0 (unreleased)

### Changed

- Overview + team pages is out of beta. Team pages now draw reporting lines,
  place each person under their own manager and show an off-page manager as a
  grey context card. Wide and deep teams continue on extra pages with that
  context kept.

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

