#!/usr/bin/env bash
set -euo pipefail

BEGIN_MARKER="# >>> amon claude session wrapper >>>"
END_MARKER="# <<< amon claude session wrapper <<<"

usage() {
  cat <<'EOF'
Usage: uninstall-claude-session-wrapper.sh [--profile PATH]

Removes the managed amon Claude session wrapper block from a shell profile.

Options:
  --profile PATH   Shell profile to update. Default: ~/.bash_profile
  -h, --help       Show this help
EOF
}

profile="${AMON_CLAUDE_PROFILE:-$HOME/.bash_profile}"

while (($# > 0)); do
  case "$1" in
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "uninstall-claude-session-wrapper.sh: --profile requires PATH" >&2
        exit 1
      fi
      profile="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "uninstall-claude-session-wrapper.sh: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$profile" ]]; then
  printf "No profile found at %s; nothing to remove.\n" "$profile"
  exit 0
fi

if ! grep -Fqx "$BEGIN_MARKER" "$profile"; then
  printf "No amon Claude session wrapper found in %s; nothing to remove.\n" "$profile"
  exit 0
fi

tmp="$(mktemp)"
awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
  $0 == begin { skip = 1; removed = 1; next }
  $0 == end { skip = 0; next }
  !skip { print }
  END {
    if (skip) {
      exit 2
    }
    if (!removed) {
      exit 3
    }
  }
' "$profile" > "$tmp"

mv "$tmp" "$profile"

printf "Removed amon Claude session wrapper from %s\n" "$profile"
printf "Reload your shell or run: source %q\n" "$profile"
