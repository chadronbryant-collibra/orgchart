# Review: how slides get uploaded

Date: 2026-11-16. Synthetic data only. Measured with the repository's own
compiler on the simple-team starter (6 cards, 5 lines).

## How it works today

1. Claude copies the template deck into the user's Drive.
2. The local compiler writes one JSON file per page (`--split-dir`) plus
   `cleanup.json`, which deletes the template's sample slides.
3. Claude sends each page file to the Slides connector's `update_presentation`.
   The connector has no file input, so Claude has to put the page's JSON into
   the tool call itself. That means the model reads the file and writes it back
   out, token by token.
4. Claude reads the deck back (`read_presentation`), pastes the result into a
   file and runs `verify`.

## What goes wrong

- **Size.** A card with its line costs about 3 KB of requests. A page with 8
  cards is about 25 KB (roughly 8,000 tokens). A full team page of 40 cards is
  about 120 KB (roughly 40,000 tokens). The model reads it once and writes it
  once, so the cost is double.
- **Where the bytes go** (compact page): text styling 26%, shape properties 18%,
  shape creation 17%, line properties 12%, line creation 10%, the rest 17%.
- **Transcription risk.** One real run truncated a page, so the model sent half
  a page and the call still succeeded. Slides accepts any valid batch. Nothing
  noticed the page was incomplete.
- **Late detection.** `verify` ran after the cleanup call. By then the template
  slides were already deleted, so a bad page could not be repaired from the
  template's own sample content.

## Options evaluated

| Option | Verdict | Why |
|---|---|---|
| One call per page file | **Already the rule.** Keep. | Limits the damage of a bad call to one page. |
| Element-count check per page | **Implemented.** | `manifest.json` now lists `expected_elements`, `slide_object_id` and `bytes` per page. `pagecheck` compares a readback with the page files and prints OK or MISSING with counts. |
| Readback-diff before cleanup | **Implemented.** | `pagecheck` checks exact element IDs, not only counts, so a swapped or half-sent page fails. It runs per page and once on the whole deck. |
| Verify before the cleanup call | **Implemented as a rule.** | `slides-writer.md` and `SKILL.md` say: run `pagecheck` after every page and send `cleanup.json` last, only when it says "Safe to send cleanup.json". |
| Smaller payloads | **Not done; recorded.** | Text styling and shape properties are 44% of the bytes and are repeated per card. A shared-style approach could cut payload by about a third, but it changes the requests of every layout and theme. That needs its own change with the theme regression tests. |
| Helper that prints page files in call-ready chunks | **Not done.** | The size problem is the model re-typing the text. Printing it in chunks puts the same tokens into the conversation twice. A page already fits in one call. Splitting a huge page across calls is possible (request order is preserved) but a partial page is exactly the failure to avoid. `pagecheck` is the safer fix. |
| Build a .pptx and import through Drive | **Not viable today.** | The repository can bind connectors inside an existing pptx but has no pptx writer, and the Drive connector's create call takes text, not a file. The model would have to send the file as encoded text, which is a larger payload with the same transcription risk. The Collibra template layout and its logos would also not carry over. A user could import a file by hand in Drive, but that is a manual step outside this skill. |
| Hard rule: no cleanup before verify | **Implemented.** | See above. The manifest's `cleanup_instruction` says it too. |

## What to tell users about time and cost

Said in `slides-writer.md` and the manual:

- Every page is sent as text through the model. A 10-page deck takes a few
  minutes. A 60-page deck takes much longer and uses many times more.
- Big decks are built in stages: overview first, then one function at a time.
  The user can stop whenever they have enough.
- Sonnet is the right default. Start a new chat for each chart. Do not ask for
  the same deck to be rebuilt to fix a small change: ask for the change.

## Follow-ups worth their own change

1. Shared styles, to cut payload by about a third (needs a theme-safe compiler
   change).
2. A connector that accepts a file path or an upload would remove the
   transcription step entirely. That is a request to the connector's owner.
3. `pagecheck` could emit a repair file containing only the missing elements.
