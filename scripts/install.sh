#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Builds and installs the standalone amon executable, then installs the optional
Claude session wrapper.

Options:
  --bin-dir PATH          Directory to install the amon command into.
                          Default: $AMON_BIN_DIR or /usr/local/bin
  --name NAME             Installed command name. Default: amon
  --profile PATH          Shell profile for the Claude wrapper.
                          Default: $AMON_CLAUDE_PROFILE or ~/.bash_profile
  --source-symlink        Install a symlink to the checkout shim instead of
                          copying the standalone zipapp artifact
  --no-claude-wrapper     Do not install the Claude session wrapper
  -h, --help              Show this help
EOF
}

bin_dir="${AMON_BIN_DIR:-/usr/local/bin}"
command_name="${AMON_COMMAND_NAME:-amon}"
profile="${AMON_CLAUDE_PROFILE:-$HOME/.bash_profile}"
install_wrapper=1
source_symlink=0

while (($# > 0)); do
  case "$1" in
    --bin-dir)
      if [[ $# -lt 2 ]]; then
        echo "install.sh: --bin-dir requires PATH" >&2
        exit 1
      fi
      bin_dir="$2"
      shift 2
      ;;
    --name)
      if [[ $# -lt 2 ]]; then
        echo "install.sh: --name requires NAME" >&2
        exit 1
      fi
      command_name="$2"
      shift 2
      ;;
    --profile)
      if [[ $# -lt 2 ]]; then
        echo "install.sh: --profile requires PATH" >&2
        exit 1
      fi
      profile="$2"
      shift 2
      ;;
    --source-symlink)
      source_symlink=1
      shift
      ;;
    --no-claude-wrapper)
      install_wrapper=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "install.sh: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$bin_dir"
target="$bin_dir/$command_name"

if [[ "$source_symlink" -eq 1 ]]; then
  ln -sfn "$ROOT/amon" "$target"
  chmod +x "$ROOT/amon"
  printf "Installed source-checkout symlink: %s -> %s\n" "$target" "$ROOT/amon"
else
  artifact="$("$ROOT/scripts/build-standalone.sh")"
  cp "$artifact" "$target"
  chmod +x "$target"
  printf "Installed standalone executable: %s\n" "$target"
fi

if [[ "$install_wrapper" -eq 1 ]]; then
  "$ROOT/scripts/install-claude-session-wrapper.sh" --profile "$profile"
else
  printf "Skipped Claude session wrapper installation.\n"
fi

printf "Make sure %s is on PATH.\n" "$bin_dir"
