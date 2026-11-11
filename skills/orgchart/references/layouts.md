# Layouts

| Name | Planner mode | When to use | Tradeoff |
| --- | --- | --- | --- |
| Simple tree | `compact_hierarchy` | A team and its reporting lines | Deep or wide teams need more pages. |
| Leadership team | `leadership_bands` | A shallow leadership view | Detailed contributor rosters need more space. |
| Departments and teams | `functional_columns` | Compare functions with uneven branches | Cross-function relationships are less prominent. |
| Matrix | `matrix_relationships` | Show a few secondary relationships | Links can make a dense page harder to read. |
| Overview + team pages (beta) | `enterprise_overview` | Navigate a larger organization by function | Team pages list people without reporting lines yet; prefer Simple tree when reporting lines matter. |

The planner recommends a starting point; verify legibility against the chosen
template. The limits are 200 people or positions, 30 pages and 8 matrix links.

Leadership team and Departments and teams group people by level or function,
so they do not draw reporting lines by design. Simple tree is the safest choice
for multi-page charts: each branch page keeps its reporting lines. Tell the user
which tradeoff applies before building.
