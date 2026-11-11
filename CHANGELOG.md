# Changelog

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

### Known limits

- Overview + team pages is in beta: its team pages list people without
  reporting lines. Use Simple tree when reporting lines matter.
- Leadership team and Departments and teams group by level or function and do
  not draw reporting lines.

