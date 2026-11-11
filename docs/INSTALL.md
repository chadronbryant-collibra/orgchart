# Install

Python 3.10 or newer is needed for local helpers. For Claude Code run
`./install.sh`. It copies the skill to your personal Claude skills directory;
repeating it refreshes files and preserves any extra destination files.

For Claude Desktop run `python3 scripts/build_desktop_zip.py`, then upload
`dist/orgchart.zip` in the skills settings. The archive has `orgchart/SKILL.md`
at its top folder. Enable the required Google Drive and Google Slides
connectors as described in the skill's connector setup guide. Connector
availability does not prove access to a particular file or roster.
