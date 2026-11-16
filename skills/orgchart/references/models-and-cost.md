# Models and cost

Sonnet is a good default. Switch only when the job calls for it.

| Task | Suggested model | Why |
| --- | --- | --- |
| List templates, tidy a CSV, small charts under about 15 people | Haiku | Quick and light for simple jobs |
| Build or update a deck (default) | Sonnet | Reliable with Slides edits at a sensible cost |
| Plan a big reorg or build a multi-org overview | Opus | Extra reasoning helps when many pieces interact |

Availability and cost depend on your plan and setup.

## Keep usage low

- Preview first. Fixing a text outline is cheaper than fixing a deck.
- The Python helpers do the layout math locally, so Claude doesn't have to.
- Send each page file once, whole. Retyping or resending a page costs the
  most. Check each page with `pagecheck` so a bad page is caught early.
- Build big decks in stages and stop when the user has what they need.
- Don't re-read whole decks. Read only what you need to check a change.
- Start a new chat for a new chart.

## Switch models

- Claude Desktop: use the model picker under the message box.
- Claude Code: type `/model`.
