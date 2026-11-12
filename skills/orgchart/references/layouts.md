# Layouts

| Name | Planner mode | When to use | Tradeoff |
| --- | --- | --- | --- |
| Simple tree | `compact_hierarchy` | A team and its reporting lines | Deep or wide teams need more pages. |
| Leadership team | `leadership_bands` | A shallow leadership view | Detailed contributor rosters need more space. |
| Departments and teams | `functional_columns` | Compare functions with uneven branches | Cross-function relationships are less prominent. |
| Matrix | `matrix_relationships` | Show a few secondary relationships | Links can make a dense page harder to read. |
| Overview + team pages | `enterprise_overview` | Navigate a larger organization by function | Readers move between the overview and several team pages. |

The planner recommends a starting point; verify legibility against the chosen
template. The per-deck limits are 1000 people or positions, 120 pages and 8 matrix links.
Rosters of 35 or more people default to Overview + team pages (unless matrix
relationships select Matrix); above 200, the recommendation includes a scale note.

Leadership team places roots in the first band, direct reports in the next,
and deeper reports in later bands. Sibling groups sit under their parent, with
reporting lines for people on the same page. Departments and teams groups people
by function without reporting lines. Matrix pages show dotted secondary links
when a clear route is available; cross-page or obstructed links appear in a
companion table. Simple tree keeps reporting lines on its branch pages.

Overview + team pages shows the top leader above one summary card per
function, then gives each function its own team pages. Team pages draw
reporting lines like Simple tree, with each manager centered over their reports. A page holds at most 8
cards across and 5 rows. When a team leader or a split branch reports to
someone on another page, that manager appears as a grey context card at the
top of the page, joined by a reporting line. A wide team repeats its leader as
a context card on each continuation page.


Function summaries show the function, position/open counts, and a third line
naming the lead. A function's lead is its first head in reporting-tree preorder;
additional heads appear as “+N more”. An unfilled head appears as “Open role”.
Summary cards remain at most 1.06 inches tall with an 8 pt text floor.

Functions with more than 40 members or more than two packed team pages gain
an overview of their heads and, for a single head, its direct-report subtrees.
Each summary includes the sub-leader's name, title, subtree population and lead.
Overviews use the same 12-summary grid as the enterprise overview, with continued
pages and safe reporting lines. Non-leaf subtrees get named team drilldowns;
leaf siblings share packs to keep very wide teams practical. Subtrees needing
more than two pages repeat this structure up to four levels. After that, plain
packing continues with navigation checkpoints before each further pair of pages.
Each position has exactly one non-context person card; summary cards reference
subtrees and grey manager cards supply context. The top leader is context when
also placed on a team page, and on repeated enterprise overview pages.

The geometry `navigation` list records each page's title, level (0 enterprise,
1 function, 2 team or deeper branch) and parent page. Continuation hints are
resolved from final person placements after all overviews have been inserted.

To estimate a roster, including one above the hard ceiling:

```sh
python3 skills/orgchart/scripts/org_chart_geometry.py plan INPUT.json
python3 skills/orgchart/scripts/org_chart_geometry.py plan INPUT.json --output-dir parts
```

`plan` reports `people`, `estimated_pages` and `fits_one_deck`. When a split is
needed, it greedily groups whole top-level reporting subtrees into parts, using
the real layout for page estimates and counting copied managers against both
limits. Oversized subtrees split one level down, recorded in `notes`. Each part
reports its title, people, pages, top nodes, owned person IDs and duplicated
roots. `overview_part` suggests a small root-and-part-leader navigation chart;
it is a suggestion, not an additional deck or duplicated roster ownership.

Optional output files contain `nodes` in flat interchange format for the
normalizer and the equivalent `people` array for direct geometry planning.
Off-part top managers are copied with `manager_id: null`, `duplicated_root: true`
and no context flag. Exclude those marked copies when reconciling ownership
across parts. Planning and file output never create presentation decks.
`estimate_pages(data)` exposes the same layout-based estimate for Python callers.
