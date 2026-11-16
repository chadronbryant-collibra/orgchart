# FAQ

## Can it see my whole company?

No. It sees only what your own Workday access allows. With the Workday roster
tools, that is the organizations Workday lets you see; with only the
self-service tools, your own line. For anything wider, it uses only the roster
you give it.

## Is there a manual?

Yes: the [user manual](../skills/orgchart/references/manual.md) has short
sections and copy-paste requests. It ships with the skill, so ask Claude for
`/orgchart help` and it will point you to it.

## Where does the deck go?

Into your Google Drive, as a copy of the template you chose. You own it.

## Can I edit it afterwards?

Yes. It's a normal Google Slides deck. You can also ask `/orgchart update
<deck link>` to make changes for you.

## What if the connectors are missing?

Follow [connector setup](../skills/orgchart/references/connector-setup.md). If
Connectors is missing or greyed out, your admin controls it, so ask your IT or
AI team. In the meantime Claude can still give you a text preview.

## Does it store my data?

This skill doesn't keep a copy of your roster anywhere. Local working files may
contain people data while you work, so delete them afterward. Your deck lives in
your own Drive. Claude conversations follow your organization's Claude
settings. See [privacy](../skills/orgchart/references/privacy.md).

## How big can a chart be?

Up to 1,000 people or positions, 120 pages and 8 matrix links per deck. Split a
bigger org into several decks, or use Overview + team pages. Simple tree also continues
branches on extra pages. Claude won't quietly leave people out.

## Can I show matrix or dotted lines?

Yes, a few. Ask for a dotted line in plain words, or use the Matrix layout.
Eight are drawn per deck; the rest are kept in a list.

## Can I change the look?

Yes: dark mode, high contrast, soft pastel, print black and white, colour by
function, or your own brand colours and font. Logos and pictures come only from
the template. See the manual.

## Can I show open, planned or resigned roles?

Yes. Each gets its own status and legend entry, so proposed positions are never
mixed up with current facts.

## Which model should I use?

Sonnet for most things. See [models and cost](../skills/orgchart/references/models-and-cost.md).

## How do I add my team's template?

Add an entry to `skills/orgchart/templates/manifest.json` with an ID, name, kind
and supported layouts, then run `python3 skills/orgchart/scripts/templates.py
validate`. Details are in [templates](../skills/orgchart/references/templates.md).
Check that your teammates can open the template file.

## Can it check a chart against Workday or my HR data?

It builds from what Workday returns and reports whether the pull was complete
or partial. It doesn't verify a roster you paste in. Check names and titles yourself.

## Who do I ask for help?

For this skill, open a GitHub issue on this repository. For connector access,
ask your IT or AI team.
