# FAQ

## Can it see my whole company?

No. With Workday it sees your own profile, your manager, your reporting chain
and your direct reports, one manager level per call. For anything wider, it
uses only the roster you give it.

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

Up to 200 people or positions, 30 pages and 8 matrix links. Split a bigger org
into several charts, or let Simple tree continue branches on extra pages. Claude won't quietly leave
people out.

## Can I show matrix or dotted lines?

Yes, a few. Use the Matrix layout. Eight secondary relationships is the limit,
and more than that makes a page hard to read.

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

Not yet checked. It can use what Workday returns for your own line, but it
doesn't verify a roster you paste in. Check names and titles yourself.

## Who do I ask for help?

For this skill, open a GitHub issue on this repository. For connector access,
ask your IT or AI team.
