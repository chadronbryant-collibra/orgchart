#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/skills/orgchart
destination="${HOME}/.claude/skills/orgchart"
mkdir -p "$destination"
cp -R "$source_dir/." "$destination/"
printf 'Installed orgchart files to %s (existing extra files preserved).\n' "$destination"
