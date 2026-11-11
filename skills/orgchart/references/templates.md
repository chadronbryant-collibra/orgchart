# Templates

Run `python3 scripts/templates.py list` from the skill folder. The manifest
lists an organization-specific Slides copy, a neutral blank canvas and synthetic
roster starters. Browse the [template folder](https://drive.google.com/drive/folders/1rhaPxUM8uC_8TzqW8hUZQc_jiNFZ_saG)
if you have access. Confirm that the selected Slides template is available to
the user and inspect its safe areas before copying. The Collibra template is
for Collibra employees; its upstream brand master is maintained separately.
The neutral option starts with a blank presentation.

To add a template, add a unique ID, name, kind and supported layouts to
`templates/manifest.json`. For a Slides template include its file ID, home,
audience and last-checked date; for a roster starter include its local path.
Follow `templates/manifest.schema.json` and run
`python3 scripts/templates.py validate`. Do not put roster data in the manifest.
