# Org chart

Need an org chart? Tell Claude who's on the team, or let it pull your direct
reports from Workday, and you'll get an editable Google Slides deck in a few
minutes. You always see a text preview first, so you can fix mistakes before
anything is created.

## What you can do

- Pick one of five layouts: Simple tree, Leadership team, Departments and
  teams, Matrix, or Overview + team pages. Claude recommends one and tells you
  the tradeoff.
- Show open, planned and resigned roles next to current people, with a legend.
- Compare a scenario against today's org without losing the original.
- Update an existing deck later: paste its link and say what changed.

## What you need

- Claude Code or Claude Desktop.
- The Google Drive and Google Slides connectors, signed in with your work
  Google account. Google Sheets and Workday are optional.
- Python 3.10 or newer if you use Claude Code (for the local preview helpers).

Not sure what you have? Run `/orgchart help`. Claude checks which connectors
it can see and tells you what's missing. See
[connector setup](skills/orgchart/references/connector-setup.md).

## Install

- Claude Code: run `./install.sh`, then start a new session. You get `/orgchart`.
- Claude Desktop: run `python3 scripts/build_desktop_zip.py`, then upload
  `dist/orgchart.zip` under Customize > Skills.

Full steps, updating and removing are in [docs/INSTALL.md](docs/INSTALL.md).

## Your first chart

1. Type `/orgchart` and say what the chart is for, who will see it and the
   as-of date.
2. Share your people: your Workday line, a Google Sheet, a CSV or a pasted
   list. Check the text preview and pick a layout.
3. Open the Slides link Claude gives you and edit it like any other deck.

The [five-minute walkthrough](docs/WALKTHROUGH.md) shows this with a sample
team. Questions are answered in the [FAQ](docs/FAQ.md).

## Templates

See your options with `python3 skills/orgchart/scripts/templates.py list`, or
type `/orgchart templates`.

- Collibra template: for Collibra employees, copied from the shared drive
  folder linked in [templates](skills/orgchart/references/templates.md). You
  need access to that folder.
- Neutral canvas: for everyone, a clean blank presentation.

## Privacy

Chart only people you are allowed to see. Do not include compensation,
performance, personal contact or protected data. Local working files may
contain people data; delete them when finished.

## Which model to use

Sonnet is the default. Haiku is fine for small charts, and Opus helps with big
reorgs. See [models and cost](skills/orgchart/references/models-and-cost.md).

## Help and feedback

Open a GitHub issue on this repository. Say what you asked for and what you
got, and leave out real names and roster data.

License: not yet chosen; all rights reserved until then.
