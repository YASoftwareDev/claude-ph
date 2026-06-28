#!/usr/bin/env sh
# Install the /ph Claude Code prompt-history search tool.
#
# From a clone:
#   ./install.sh
# Or one-line:
#   curl -fsSL https://raw.githubusercontent.com/YASoftwareDev/claude-ph/main/install.sh | sh
#
# Copies two files into your Claude Code config; nothing else is touched.
set -eu

RAW="https://raw.githubusercontent.com/YASoftwareDev/claude-ph/main"
SCRIPTS="${HOME}/.claude/scripts"
COMMANDS="${HOME}/.claude/commands"

mkdir -p "$SCRIPTS" "$COMMANDS"

# Resolve the directory this script lives in (empty when piped through curl).
SRC=""
case "${0:-}" in
  */*) d=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) ;;
  *)   d="" ;;
esac
[ -n "$d" ] && [ -f "$d/ph.py" ] && SRC="$d"

install_file() {  # $1 = filename, $2 = destination dir
  if [ -n "$SRC" ] && [ -f "$SRC/$1" ]; then
    cp "$SRC/$1" "$2/$1"
  else
    curl -fsSL "$RAW/$1" -o "$2/$1"
  fi
  echo "  installed $2/$1"
}

echo "Installing claude-ph..."
install_file ph.py "$SCRIPTS"
install_file ph.md "$COMMANDS"
echo "Done. Restart Claude Code, then run:  /ph <terms>"
