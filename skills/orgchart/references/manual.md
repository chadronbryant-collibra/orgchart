# Org Chart Creator: user manual

You tell Claude who is on the team. You get an editable Google Slides org chart.
You always see a text preview first, so mistakes are fixed before a deck exists.

Every example below can be copied into the chat as it is. Names and numbers
are made up.

## Contents

1. [Quick start](#1-quick-start)
2. [Giving Claude your people](#2-giving-claude-your-people)
3. [Choosing a layout](#3-choosing-a-layout)
4. [Statuses and the legend](#4-statuses-and-the-legend)
5. [The at-a-glance page](#5-the-at-a-glance-page)
6. [Adding, changing and removing positions](#6-adding-changing-and-removing-positions)
7. [Proposed roles](#7-proposed-roles)
8. [Dotted lines](#8-dotted-lines)
9. [Current vs planned](#9-current-vs-planned)
10. [Themes and branding](#10-themes-and-branding)
11. [Updating a deck you already have](#11-updating-a-deck-you-already-have)
12. [Large organizations](#12-large-organizations)
13. [Privacy](#13-privacy)
14. [Troubleshooting](#14-troubleshooting)
15. [What Claude will check with you first](#15-what-claude-will-check-with-you-first)

## 1. Quick start

You need Claude with the Google Drive and Google Slides connectors signed in
with your work Google account. Type `/orgchart help` to see what Claude can
reach in your setup.

1. Type `/orgchart`.
2. Answer three questions: is the chart current, planned or both, who will see
   it, and what is the as-of date.
3. Give Claude your people (section 2).
4. Read the text preview. Fix anything wrong. Pick a layout.
5. Open the Slides link Claude gives you.

Try this:

> /orgchart I need a current org chart for my leadership meeting on 1 March. My people are in the CSV I'm pasting below.

Building a deck takes a few minutes. Big decks take longer (section 12).

## 2. Giving Claude your people

Each person needs a name, a title and who they report to. Function and status
help but are optional.

| Source | What it covers |
|---|---|
| Pasted list or typed list | Anyone you are allowed to see. |
| CSV file | Anyone in the file. |
| Google Sheet | Anyone in the sheet. |
| Workday roster tools (default when available) | Any organization your Workday access lets you see, by name, one or two levels deep, as of today. Claude tells you how many Workday calls it will make first. |
| Workday self-service tools | **Only your own line:** you, your manager, your reporting chain and your direct reports. |
| BigQuery (People Solutions only) | Any organization in the People data, for people who already have that access. |

If Workday can't give you the organization, export a team or
supervisory-organization report from Workday into a Sheet or CSV and give that
to Claude.

Columns to use: `node_id`, `display_name`, `title`, `manager_node_id`,
`function`, optional `status`. A blank manager means the top of the chart.

Try this:

> Here is my team. Alex Rivera, VP Product, reports to nobody. Sam Lee, Director Design, reports to Alex Rivera. Jo Kim, Director Research, reports to Alex Rivera.

Claude will not guess a missing manager. It will ask.

## 3. Choosing a layout

Claude recommends one and tells you what you give up. You can ask for another.

| Layout | Good for |
|---|---|
| Simple tree | One team and its reporting lines. |
| Leadership team | A shallow view of leaders in bands. |
| Departments and teams | Comparing functions side by side. No reporting lines. |
| Matrix | A few dotted-line relationships on top of the hierarchy. |
| Overview + team pages | Large organizations: a summary page, then team pages. |

Rule of thumb: under 35 people, Simple tree. Over that, Overview + team pages.

Try this:

> Show me the options for 40 people and recommend one.
> Use the Departments and teams layout instead.

## 4. Statuses and the legend

Every box has a status. Statuses look different, so nobody mistakes a plan for a
fact.

| Status | Looks like | Counts as headcount |
|---|---|---|
| Filled | Solid box | +1 |
| Open | Dashed box, says "Open role" | 0 |
| Planned | Dotted box, says "Planned" | 0 |
| Resigned | Shaded box | -1 |
| Other | A label you choose | 0 |

Contractors get a "Contingent" marker.

Each page has a legend at the bottom that explains only the meanings used on
that page. The meaning never depends on colour alone, so it still reads on a
black and white printout.

Try this:

> Mark the Customer Advisor role as open.
> Show the contractors as contingent.

## 5. The at-a-glance page

An optional first page with the numbers: positions, filled, open, planned,
resigned and contingent counts, dotted-line links, and headcount by function.
It is off unless you ask.

Try this:

> Add an at-a-glance summary page at the front.

Counts match the chart itself. The other pages are not changed, except that
page numbers move up by one.

## 6. Adding, changing and removing positions

Say what you want in plain words. Claude turns it into an edit list, checks the
people exist, and shows you a summary before building anything. Your original
roster is never overwritten.

Try these:

> Add a Director of Analytics under the VP of Product.
> Move Gamma to report to Delta.
> Change Epsilon's title to Senior Director.
> Remove the open Operations Lead role.
> Remove Delta and move their team to Beta.

If the person you remove has people reporting to them, Claude stops and asks:
move them to someone else, remove them too, or cancel. Claude never picks for you.

## 7. Proposed roles

A proposed role is a position that does not exist yet. It shows as a planned box
with a short note, for example "Proposed: assumes budget approval".

Try this:

> Add a planned Director of Analytics under the VP of Product, assuming budget is approved next cycle.
> Mark Epsilon's role as proposed.

Say why it is proposed. If you do not, Claude asks for a short reason or writes
"assumption not yet confirmed". Planned roles never count as headcount.

## 8. Dotted lines

Dotted lines show a second relationship, such as "works with". A person still
has one manager.

Try this:

> Add a dotted line from Gamma to Eta.
> Remove the dotted line between Beta and Delta.

Good to know:

- Both people must exist. A line from A to B is the same as from B to A.
- A deck draws up to 8 dotted lines. Extra ones are kept in a list, and Claude
  tells you how many were drawn and how many were listed.

## 9. Current vs planned

Ask for the comparison and Claude shows today's org next to the plan, with the
changes in words and the headcount change.

Try this:

> Show current vs planned.

You get, for example: "1 added (1 proposed), 1 moved, 1 removed, dotted lines
1 to 2; headcount 7 to 7". To put both in a deck, Claude builds one deck from
each, or puts the changes on a notes page.

To undo, drop a change and ask again. Today's org is always kept.

## 10. Themes and branding

A theme changes colours, fonts and box shapes. It never changes who is in the
chart or where they sit. The result is still normal Slides shapes you can edit.

| Say | You get |
|---|---|
| "Use the Collibra look" | Collibra colours (Collibra employees only). |
| "Plain grey" | Neutral theme for any template. |
| "Calm blue" | Corporate blue. |
| "Dark mode" | Light text on dark navy. |
| "Accessible" or "high contrast" | Black on white, easiest to read. |
| "Soft pastel" | Friendly colours for all-hands. |
| "Colour each department differently" | One colour per function. |
| "Black and white print" | Greys only, patterns carry the meaning. |

Try these:

> Make it dark mode.
> Use our brand green #1B7F5C as the accent.
> Make it look like our brand: dark navy and orange, font Roboto.
> Add "Acme Corp, Confidential" at the bottom of every page.

Claude shows you the palette before building. Limits:

- Logos and pictures come only from the template. Choose or prepare a template
  that already holds your logo.
- Colour by function has no key on the slide. Tell readers which colour is which.
- Boxes keep their size and spacing. A theme does not move things.

## 11. Updating a deck you already have

Paste the deck link and say what changed.

Try this:

> /orgchart update https://docs.google.com/presentation/d/EXAMPLE and add two open roles under Person Beta.

Claude works from your roster, not by reading the pictures. If you changed the
deck by hand, tell Claude, or give the current roster, so your edits are not lost.

## 12. Large organizations

- One deck holds up to 1,000 people and 120 pages.
- Big functions get their own overview, then team pages.
- Claude builds in stages: overview first, then one function at a time. You can
  stop at any stage.
- Bigger than the limit? Claude proposes a split into several decks and agrees
  it with you first.
- Every page is written by sending Slides instructions. That takes time and
  usage: a small chart is a few minutes, a hundred-page deck is much longer. Use
  Sonnet for decks, and start a new chat for each chart.

Try this:

> Plan how to split this 1,400 person roster into decks. Don't build anything yet.

## 13. Privacy

- Chart only people you are allowed to see.
- Claude leaves out pay, performance, personal contact details and other
  protected information, even if your file has them.
- Working files on your computer may hold names. Delete them when you finish.
- The deck goes to your own Google Drive. Claude confirms where before it
  creates anything, and confirms before anything is shared.
- Use made-up names when you are only trying things out.

## 14. Troubleshooting

| Problem | What to do |
|---|---|
| Claude says Drive or Slides is missing | Connect them under Connectors (see the connector setup page in this skill). If greyed out, ask IT. Claude can still give a text preview. |
| Workday says you can't see an organization | That's your Workday access. Claude won't work around it. Ask for a Sheet or CSV from someone who can see it. |
| Claude says the pull is partial | Some units were too deep or a page stopped. Claude lists what's missing; add those people from a Sheet or ask for depth 2 on that unit. |
| "I could not find X in the roster" | The name or ID is not in your roster. Fix the spelling or add the person. |
| Removal stopped with a list of names | That person has reports. Choose move or remove them too. |
| A manager is missing for someone | Tell Claude who they report to. It will not guess. |
| Text is cut off in a box | Tell Claude. It checks text fits and says plainly if a card cannot fit. Shorter titles help. |
| A page looks half built | Say so. Claude checks every page against what it built, and repairs only the missing parts. |
| The deck link opens in the wrong place | Ask Claude to copy it to My Drive. |
| Too many dotted lines | Only 8 are drawn. The rest are in a list. |
| Colours look wrong | Ask for a different theme, or "high contrast". |

## 15. What Claude will check with you first

Claude says the plan back and waits for your yes before:

- removing a position, and how to handle the people below it
- a move that changes a manager's team by more than a few people
- a proposed role with no reason given
- more than about ten edits at once
- a name or title that matches more than one position
- building a big deck: the page plan and the stages
- copying a template or creating a deck in your Drive

Claude does not need to ask before showing a preview. Nothing is created until
you have seen it.
