# Native Slides writer

Use this recipe after the user has reviewed the outline and page plan. Confirm
account, destination, template access, and connector availability first. The
compiler is local; it does not create or update a presentation.

1. Copy the selected Google Slides template with Drive `copy_file` into the
   user's chosen folder or My Drive. Use the returned presentation ID. For the
   neutral option, create a blank presentation in that destination. Inspect the
   page size and template safe areas before writing.
2. Call `read_presentation` on that copy with fields `slides.objectId`. Save the
   response as `existing.json`. This lets the compiler remove sample slides only
   after creating the replacement slides. Do not supply another deck's readback.
3. Normalize the roster and generate and validate geometry, as in SKILL.md.
   Geometry uses inches on a 13.333 by 7.5 inch canvas. If the destination differs,
   resolve that mismatch before writing. Keep roster files private and temporary.
4. Compile the geometry. The Collibra template's layout ID is in the manifest:

   ```sh
   python3 scripts/slides_requests.py compile orgchart-work/geometry.json \
     --theme collibra-2026 --layout-id g3efe399732d_0_346 \
     --existing-slides orgchart-work/existing.json \
     --output orgchart-work/requests.json
   ```

   For neutral use `--theme neutral` and omit `--layout-id`. The command prints
   counts and writes `presentation_requests`, an ordered array of request arrays.
   The default chunk limit is 400; set `--chunk` if needed. Each chunk depends on
   earlier chunks, so keep their order. Review counts before submitting.
5. For each chunk, call Slides `update_presentation` with the copied
   `presentationId` and that chunk as `requests`. Send one call at a time in
   order. These are raw Google Slides batchUpdate requests, not a wrapper around
   the entire compiler output.
6. Run `python3 scripts/slides_requests.py fields` and use its exact output as
   the `read_presentation` fields mask. Save the response as `readback.json`.
   Then run:

   ```sh
   python3 scripts/slides_requests.py verify orgchart-work/geometry.json orgchart-work/readback.json
   ```

   Resolve every failure. Verification checks expected slide and card IDs, card
   shape and starting text, and both attached line endpoints and site indexes.
   It does not prove the saved slide looks right or that a line follows a move.
7. Fetch a thumbnail for one slide per page and inspect readability, completeness,
   line placement and overlap. Review actual endpoints. Text overflow means repaginate or adjust the layout; card text has an 8 pt floor. Cards and lines must remain editable
   native elements, never flattened images.
8. Test attachment on a disposable card: use `updatePageElementTransform` with
   `applyMode: RELATIVE` to move one card, read back and inspect its line, then
   apply the inverse transform and read back again. Read back the restored card and line and record the result. Do this only on the intended copied deck.
9. Return the deck link and the completed checks. Repeated drilldown leaders are
   labeled context and excluded from totals. Legends show only meanings used on
   the page, with text and pattern as well as color.

If any write has an uncertain outcome, read back the same presentation before
any retry. Reconcile which requests took effect; never resend a chunk blindly.
If native writing is unavailable, return the local preview and say no deck was
created.

The first live Slides test on 2026-11-11 used a synthetic future-state plan
and a Collibra template copy. One batch created seven cards and six attached
lines and deleted 59 sample slides. Readback confirmed the intended endpoints.
BENT attached lines rendered correctly and followed a card moved with a RELATIVE
transform; restoring the card restored the line transform exactly. Slides may
omit a zero connection site index from readback; verification treats it as zero.
The tested 2.0 by 0.72 inch cards fit a 10 pt bold name and 9 pt other lines,
while 14.4 pt text overflowed. The compiler uses BENT by default; use
`--connector-category STRAIGHT` only when a straight line is intended.
