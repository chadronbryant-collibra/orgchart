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

Plugin install:

```
/plugin marketplace add chadronbryant-collibra/orgchart
/plugin install orgchart@orgchart
```

Plugin skills are named after their plugin, so this one is `/orgchart:orgchart`.
Plain `/orgchart` also works as long as nothing else on your machine uses that
name. Prefer the personal install above if you want the short name every time.

## Claude Desktop

Download `orgchart.zip` from the latest GitHub release, or build it yourself:

```sh
python3 scripts/build_desktop_zip.py
```

Then open Claude, select Customize > Skills, and upload the zip. Keep the zip as
it is: it holds one `orgchart` folder with `SKILL.md` inside, which is the
layout Claude expects. Skills that run scripts need code execution, so if
uploading is greyed out, ask your admin whether skills and code execution are
turned on for your organization.

## Everyone in your organization

Claude Team and Enterprise owners can give the skill to everyone at once.
Download `orgchart-plugin-v<version>.zip` from the latest GitHub release (or
build it with `python3 scripts/build_plugin_zip.py`), then go to
Organization settings > Plugins & skills > Add > Upload a plugin. Set its
availability to "Available to install" or "Installed by default". It then
reaches claude.ai, Claude Desktop, Cowork and Claude Code sessions that sync
your account's plugins. Uploading a newer zip with the same plugin name
replaces the old one.

You can also upload the same zip just for yourself under Customize > Plugins >
Add > Upload plugin, share it with a few people to try it, and use Publish to
org when it's ready, if your organization allows that.

Skills that run scripts need code execution, so check it's on for your
organization.

## Check it worked

Start a new chat or session and type `/orgchart help`. Claude should explain
the flow. When you start a chart with `/orgchart`, its first step checks which
connectors it can see and walks you through any that are missing. In Claude Code you can also run
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
