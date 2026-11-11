# Install

Pick the client you use. Claude Code needs Python 3.10 or newer for the local
preview helpers. Claude Desktop runs skills in its own sandbox, so you don't
need Python for the skill itself (only to build the zip).

You also need the Google Drive and Google Slides connectors. See
[connector setup](../skills/orgchart/references/connector-setup.md).

## Claude Code

Personal install:

```sh
./install.sh
```

This copies the skill to your personal Claude skills folder and gives you
`/orgchart`. Running it again refreshes the files and keeps any extra files you
added.

Plugin install (to be confirmed in install test):

```
/plugin marketplace add chadronbryant-collibra/orgchart
/plugin install orgchart@orgchart
```

With the plugin, the command may appear namespaced as `/orgchart:orgchart`.
That is also to be confirmed in install test.

## Claude Desktop

Build the zip, then upload it:

```sh
python3 scripts/build_desktop_zip.py
```

Then select Customize > Skills and upload `dist/orgchart.zip`. Once releases
are published you can download the zip from GitHub Releases instead. Both the
upload path and the release download are to be confirmed in install test.

## Check it worked

Start a new chat or session and type `/orgchart help`. Claude should explain
the flow and say which connectors it can see. In Claude Code you can also run
`python3 skills/orgchart/scripts/templates.py list` to check the helpers.

## Update

Pull the latest version of this repository and run `./install.sh` again. For
Desktop, rebuild the zip and upload it again. For the plugin, use `/plugin`
to update it.

## Remove

- Claude Code personal install: delete the `orgchart` folder from your personal
  Claude skills folder (`~/.claude/skills/orgchart`).
- Plugin: `/plugin uninstall orgchart@orgchart`.
- Claude Desktop: remove the skill under Customize > Skills.
