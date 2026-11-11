# Five-minute walkthrough

We'll build a chart for a small made-up team. Everything here is sample data.
The text previews below are real output from the starter files.

## 1. Say what you want

You type:

> /orgchart I need a current org chart for my leadership meeting on 1 March.

Claude checks that Google Drive and Slides are connected, then asks three
things: is this a current, planned or mixed view, who will see it, and what is
the as-of date. It also asks where your people list comes from: Workday, a
Google Sheet, a CSV or a pasted list. For this walkthrough, say you'd like to
use the simple team starter.

## 2. Check the preview

Claude cleans up the list and shows a text outline before it touches Slides.
You can run the same steps yourself from the `skills/orgchart` folder:

```sh
mkdir -p ./orgchart-work
python3 scripts/normalize_org_chart.py normalize examples/starters/simple-team.json --output ./orgchart-work/render.json --receipt ./orgchart-work/receipt.json
python3 scripts/preview_org_chart.py outline ./orgchart-work/render.json
```

```
Outline:
Person Alpha | Chief Demonstration Officer [filled]
  Person Beta | VP Product Examples [filled]
    Person Gamma | Director Product Design [filled]
    Open | Product Operations Lead [open]
  Person Delta | VP Customer Examples [filled]
    Person Epsilon | Director Customer Programs [filled]
Totals: filled 5, open 1, planned 0, resigned 0, other 0
Recommended: Simple tree | The roster fits a conventional manager hierarchy.
Page plan: 1 page(s), Simple tree
  org-page-compact-hierarchy-1-eb05958f: Organization chart
```

Is anyone missing or in the wrong place? Tell Claude now. It's much quicker
to fix here than in the deck.

## 3. Choose a layout and template

Claude recommends a layout and says what you give up with it. Here it suggests
Simple tree. You can pick another: Leadership team, Departments and teams,
Matrix, or Overview + team pages. It also offers a template. Run
`python3 scripts/templates.py list` to see them. Collibra employees can use the
Collibra template; everyone can use the neutral canvas.

## 4. Create the deck

Say "go ahead". Claude copies the template into your Drive and builds the cards,
connector lines and legend in one batch. It then checks the counts and gives
you a link. If it can't write to Slides, it tells you no deck was created and
leaves you with the preview.

Open the link. It's a normal Slides deck, so move boxes, change text or
restyle as you like.

## 5. Make changes later

Paste the deck link and say what changed, for example "Product Operations Lead
was filled by a new hire". Claude looks at the deck first and then updates it.
You can also ask it to compare a scenario against the current chart; the
original stays as the baseline.

## Try a planned org

The `future-state-plan` starter adds a planned role and relationships that
cross the reporting line:

```sh
python3 scripts/normalize_org_chart.py normalize examples/starters/future-state-plan.json --output ./orgchart-work/plan.json --receipt ./orgchart-work/plan-receipt.json
python3 scripts/preview_org_chart.py outline ./orgchart-work/plan.json
```

```
Totals: filled 5, open 1, planned 1, resigned 0, other 0
Recommended: Matrix | The input contains explicit non-hierarchical relationships.
Page plan: 2 page(s), Matrix
```

The planned role shows with its own status and legend entry, apart from
today's facts.

The preview doesn't create a deck. Delete `./orgchart-work` when you're done,
since working files can hold people data. Use fresh file names for each run.
