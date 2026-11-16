# Themes: changing how the chart looks

A theme controls colours, fonts, card shape and status styling. It never changes who is in the chart or how it is laid out. Every theme produces ordinary Google Slides shapes and lines that you can keep editing by hand. Charts are never flattened into pictures.

## Built-in themes

Run `python3 scripts/slides_requests.py themes` to list them, and `themes --preview` (or `--preview NAME`) to print each palette as text.

| Theme | Look |
| --- | --- |
| `collibra-2026` | Collibra brand colours. For the Collibra template, which is for Collibra employees. |
| `neutral` | Plain grey and black. Works on any template. |
| `corporate-blue` | Calm blues, square corners. |
| `dark-mode` | Light text on a dark navy page. |
| `high-contrast` | Black on white, deep blue accent, AAA text contrast. |
| `soft-pastel` | Lilac, peach and mint on white. |
| `function-colors` | One bold colour per function. Best with the functional layout. |
| `print-mono` | Black, white and grey only. Patterns carry the meaning. |

## How to ask for one

Say it in your own words. Claude picks the theme and the options.

- "Make it dark mode."
- "Use the accessible version, I need it readable on a projector."
- "Something friendly and pastel for the all-hands."
- "Colour each department differently."
- "It will be printed in black and white."
- "Use our brand green, #1B7F5C, as the accent."
- "Add 'Acme Corp, Confidential' at the bottom of every page."

If you have a brand guide, paste the colours and the font name. Claude turns them into a theme file and shows you the palette before building the deck.

## What can be changed

- Text colours: main text and secondary text.
- Card fill, outline colour and line pattern for each status: filled, open role, planned, resigned, other, context and contingent.
- Reporting line colour and the dotted "works with" line colour.
- The accent colour, which drives open and planned outlines and the dotted line. Use `--accent '#RRGGBB'` to change just this.
- Font family (any Google Slides font name), title size, colour and alignment (left, centre, right), and bold or plain.
- Card corners: round or square.
- Page background colour (solid colour only).
- Table heading and body fills in the "works with" relationship table.
- An optional footer line on every page. Use `--footer 'text'`.
- Colour by function: filled cards take a colour from a palette, cycled in alphabetical order of function name. Turn it on with `--color-by-function`, or off with `--no-color-by-function`. Open, planned and other statuses keep their own look so they stay recognisable.

## Accessible choices

- Status never relies on colour alone. Open roles say "Open role" and planned roles say "Planned" on the card. Resigned, open, planned and contingent cards also use different outline patterns (solid, dashed, dotted, dash-dot, long dash-dot). The legend uses the same patterns.
- The six newer themes pass WCAG AA text contrast (4.5 to 1) on every fill they use, and the tests check this. `high-contrast` meets AAA (7 to 1).
- Any custom theme is checked when you compile. Faint text, faint outlines, and statuses that share a line pattern are reported as plain-language warnings. A warning does not stop the build, so read it and decide.
- `collibra-2026` and `neutral` are kept exactly as they were so existing charts do not change. A few of their secondary text colours fall below AA on some fills. Choose `high-contrast` or `corporate-blue` when accessibility matters.
- Prefer dark text on light cards, or the reverse. Avoid mid-tone fills, which fail in both directions.

## Your own theme

Save a JSON file with only the settings you want to change. It is merged over a base theme: `--theme NAME` if you pass one, else the file's `"extends"` value, else `neutral`.

```json
{
  "extends": "corporate-blue",
  "accent": "#1B7F5C",
  "font": "Roboto",
  "colors": { "ink": "#10261C", "line": "#1B7F5C" },
  "statuses": {
    "filled": { "fill": "#F4FAF7", "outline": "#8FC3AB" },
    "open": { "dash": "LONG_DASH" }
  },
  "title": { "size": 22, "align": "CENTER" },
  "card_corners": "round",
  "footer": { "text": "Example Co | Internal" }
}
```

Build with:

```bash
python3 scripts/slides_requests.py compile geometry.json --theme-file my-theme.json --output requests.json
```

Colours are six hex digits with an optional `#`. `@accent` (also `@ink`, `@muted`) can stand in for a colour. Line patterns are SOLID, DOT, DASH, DASH_DOT, LONG_DASH, LONG_DASH_DOT, SYS_DASH and SYS_DOT. A function palette looks like `"color_by_function": {"enabled": true, "palette": [{"fill": "#FFD6A5", "outline": "#9C4A00"}, {"fill": "#CFF5C0", "outline": "#2E7D32"}]}` with 2 to 12 pairs. The full field list is in `templates/themes/theme.schema.json`.

Mistakes come back in plain words, for example: `The colour 'navy' in 'colors.ink' is not a hex colour. Write six hex digits such as #1A2B3C`, or `Unknown setting 'colours'. Did you mean 'colors'?`.

Dark themes need a function palette of their own (dark fills, light outlines). `dark-mode` ships one.

## Logos and backgrounds

A theme sets only a solid page colour. Logos, photos and background art come from the template slide layout you build on. Pick or prepare a template whose layout already holds the logo, and the chart is drawn over it. If the theme sets a background colour it covers the layout's background, so leave that unset (as every light theme does) when you want the layout's artwork to show.

Dark themes (such as `dark-mode`) go on the blank canvas. On the Collibra template the logo is dark, so a dark background would hide it; compile stops with a plain message if you try.

## Limits

- The Collibra template and `collibra-2026` theme are for Collibra employees. Other people should use another theme on a blank or their own template.
- Images must come from the chosen template layout. The skill does not insert pictures or logos on its own.
- Charts are not flattened to images. Everything stays an editable shape, line or table.
- Fonts must exist in Google Slides. An unknown font name falls back to a default in Slides.
- Card sizes, spacing and layout are fixed by the layout, not by the theme.
- Colour by function has no on-slide key. It works best in the functional layout, where each panel is named. Cards in the other layouts show the colour, so say which function is which in the deck.
