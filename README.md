# Org chart

Need an org chart? Let Claude pull it from Workday, or tell it who's on the
team, and you'll get an editable Google Slides deck in a
few minutes. You always see a text preview first, so you can fix mistakes before
anything is created.

Claude pulls from Workday by default and sees only what your own Workday access
allows. For anything else, give Claude a Sheet, a CSV or a pasted list.

## What you can do

- Pick one of five layouts: Simple tree, Leadership team, Departments and
  teams, Matrix, or Overview + team pages. Claude recommends one and tells you
  the tradeoff.
- Show open, planned and resigned roles next to current people, with a legend.
- Add, move, change or remove positions in plain words, add proposed roles and
  dotted lines, and see current vs planned side by side.
- Add an at-a-glance summary page with counts by status and function.
- Change the look: dark mode, high contrast, soft pastel, black and white print,
  colour by function, or your own brand colours and font.
- Update an existing deck later: paste its link and say what changed.

New here? Read the [user manual](skills/orgchart/references/manual.md). It has
short sections and requests you can copy.

## Who it can chart

Workday is the default, and Workday security decides what you see. With the
Workday roster tools, Claude can chart any organization Workday lets you see,
one or two levels deep. With only the self-service tools, it covers your own reporting line: you, your manager, your reporting chain and your direct
reports. For anyone else, give Claude a Google Sheet, a CSV or a pasted list.

## What you need

- Claude Code or Claude Desktop.
- The Google Drive and Google Slides connectors, signed in with your work
  Google account. Workday is recommended; Google Sheets is optional.
- Python 3.10 or newer if you use Claude Code (for the local preview helpers).

Not sure what you have? Run `/orgchart help`. Claude explains what it can do
and checks which connectors it can see when you start a chart. See
[connector setup](skills/orgchart/references/connector-setup.md).

## Install

Pick the line that matches how you got this.

- **Your organization installed the plugin** (an owner uploaded the plugin zip):
  nothing to install. Start a new chat and type `/orgchart help`.
- **You have the plugin zip and want it for yourself:** in Claude, open
  Customize > Plugins > Add > Upload plugin and choose
  `orgchart-plugin-v<version>.zip`.
- **You cloned the repository, Claude Code:** run `./install.sh`, then start a
  new session. You get `/orgchart`.
- **You cloned the repository, Claude Desktop:** run
  `python3 scripts/build_desktop_zip.py`, then upload `dist/orgchart.zip` under
  Customize > Skills.

The first two need no repository files. The last two need the repository.
Full steps, updating and removing are in the repository's
`docs/INSTALL.md`.

## Your first chart

1. Type `/orgchart` and say what the chart is for, who will see it and the
   as-of date. Or just type `/orgchart` and pick from the menu.
2. Name the organization to pull from Workday, or share a Google Sheet, a
   CSV or a pasted list. Check the text preview and pick a layout.
3. Open the Slides link Claude gives you and edit it like any other deck.

Ask `/orgchart help` for a tour. Common questions are in the repository's
`docs/FAQ.md`.

## Templates

Type `/orgchart templates` to see your options.

- Collibra template: for Collibra employees, copied from the shared drive
  folder linked in [templates](skills/orgchart/references/templates.md). You
  need access to that folder.
- Blank canvas: for everyone, a blank 16:9 deck in any of the other themes, such as dark mode or high contrast.

## Privacy

Chart only people you are allowed to see. Do not include compensation,
performance, personal contact or protected data. Local working files may
contain people data; delete them when finished.

## Which model to use

Sonnet is the default. Haiku is fine for small charts, and Opus helps with big
reorgs. See [models and cost](skills/orgchart/references/models-and-cost.md).

## Help and feedback

Open a GitHub issue on the repository
(chadronbryant-collibra/orgchart). Say what you asked for and what you
got, and leave out real names and roster data.

License: not yet chosen; all rights reserved until then.
