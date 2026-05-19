#!/usr/bin/env bash
set -euo pipefail

BEGIN_MARKER="# >>> amon claude session wrapper >>>"
END_MARKER="# <<< amon claude session wrapper <<<"

usage() {
  cat <<'EOF'
Usage: install-claude-session-wrapper.sh [--profile PATH] [--print]

Installs a shell function named `claude` that injects a fresh lowercase
--session-id into each new Claude invocation.

Options:
  --profile PATH   Shell profile to update. Default: ~/.bash_profile
  --print          Print the managed shell block without modifying a profile
  -h, --help       Show this help
EOF
}

profile="${AMON_CLAUDE_PROFILE:-$HOME/.bash_profile}"
print_only=0

while (($# > 0)); do
  case "$1" in
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "install-claude-session-wrapper.sh: --profile requires PATH" >&2
        exit 1
      fi
      profile="$2"
      shift 2
      ;;
    --print)
      print_only=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "install-claude-session-wrapper.sh: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

read -r -d '' WRAPPER_BLOCK <<'EOF' || true
# >>> amon claude session wrapper >>>
claude() {
  local amon_claude_arg
  for amon_claude_arg in "$@"; do
    case "$amon_claude_arg" in
      --session-id|--session-id=*|--resume|--continue)
        command claude "$@"
        return
        ;;
    esac
  done

  local amon_claude_session_id
  amon_claude_session_id="$(uuidgen | tr '[:upper:]' '[:lower:]')" || return
  command claude --session-id "$amon_claude_session_id" "$@"
}
# <<< amon claude session wrapper <<<
EOF

if [[ "$print_only" -eq 1 ]]; then
  printf "%s\n" "$WRAPPER_BLOCK"
  exit 0
fi

mkdir -p "$(dirname "$profile")"
tmp="$(mktemp)"
if [[ -f "$profile" ]]; then
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "$profile" > "$tmp"
else
  : > "$tmp"
fi

{
  cat "$tmp"
  if [[ -s "$tmp" ]]; then
    printf "\n"
  fi
  printf "%s\n" "$WRAPPER_BLOCK"
} > "$tmp.new"

mv "$tmp.new" "$profile"
rm -f "$tmp"

printf "Installed amon Claude session wrapper into %s\n" "$profile"
printf "Reload your shell or run: source %q\n" "$profile"
