#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: uninstall.sh [options]

Removes the installed amon command and the optional Claude session wrapper.

Options:
  --bin-dir PATH          Directory containing the installed amon command.
                          Default: $AMON_BIN_DIR or ~/bin
  --name NAME             Installed command name. Default: amon
  --profile PATH          Shell profile for the Claude wrapper.
                          Default: $AMON_CLAUDE_PROFILE or ~/.bash_profile
  --no-claude-wrapper     Do not remove the Claude session wrapper
  --force                 Remove the command path even if it cannot be
                          identified as an amon executable
  -h, --help              Show this help
EOF
}

bin_dir="${AMON_BIN_DIR:-$HOME/bin}"
command_name="${AMON_COMMAND_NAME:-amon}"
profile="${AMON_CLAUDE_PROFILE:-$HOME/.bash_profile}"
remove_wrapper=1
force=0

while (($# > 0)); do
  case "$1" in
    --bin-dir)
      if [[ $# -lt 2 ]]; then
        echo "uninstall.sh: --bin-dir requires PATH" >&2
        exit 1
      fi
      bin_dir="$2"
      shift 2
      ;;
    --name)
      if [[ $# -lt 2 ]]; then
        echo "uninstall.sh: --name requires NAME" >&2
        exit 1
      fi
      command_name="$2"
      shift 2
      ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "uninstall.sh: --profile requires PATH" >&2
        exit 1
      fi
      profile="$2"
      shift 2
      ;;
    --no-claude-wrapper)
      remove_wrapper=0
      shift
      ;;
    --force)
      force=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "uninstall.sh: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

target="$bin_dir/$command_name"
removed_command=0

is_amon_executable() {
  [[ -x "$target" ]] || return 1
  "$target" --help 2>/dev/null | grep -Fq "Monitor active Claude and Codex automation sessions."
}

if [[ -e "$target" || -L "$target" ]]; then
  if [[ "$force" -eq 1 ]]; then
    rm -f "$target"
    removed_command=1
  elif [[ -L "$target" && "$(readlink "$target")" == "$ROOT/amon" ]]; then
    rm -f "$target"
    removed_command=1
  elif is_amon_executable; then
    rm -f "$target"
    removed_command=1
  else
    printf "Refusing to remove %s because it does not look like amon.\n" "$target" >&2
    printf "Use --force to remove it anyway.\n" >&2
    exit 1
  fi
fi

if [[ "$removed_command" -eq 1 ]]; then
  printf "Removed installed command: %s\n" "$target"
else
  printf "No installed command found at %s; nothing to remove.\n" "$target"
fi

if [[ "$remove_wrapper" -eq 1 ]]; then
  "$ROOT/scripts/uninstall-claude-session-wrapper.sh" --profile "$profile"
else
  printf "Skipped Claude session wrapper removal.\n"
fi
