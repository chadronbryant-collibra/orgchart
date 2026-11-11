# Five-minute preview

From `skills/orgchart`, run:

```sh
mkdir -p ./orgchart-work
python3 scripts/normalize_org_chart.py normalize examples/starters/simple-team.json --output ./orgchart-work/render.json --receipt ./orgchart-work/receipt.json
python3 scripts/preview_org_chart.py outline ./orgchart-work/render.json
python3 scripts/templates.py list
```

Review the synthetic team's outline, totals and page plan. Ask `/orgchart` to
choose a template and layout and, once connectors are available, create an
editable deck. This local preview does not create a presentation. Remove the
working folder when finished. Use fresh output names for another run.
