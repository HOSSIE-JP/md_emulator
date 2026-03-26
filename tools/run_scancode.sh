#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${TYPECODE_LIBMAGIC_PATH:-}" && -f "/opt/homebrew/opt/libmagic/lib/libmagic.dylib" ]]; then
  export TYPECODE_LIBMAGIC_PATH="/opt/homebrew/opt/libmagic/lib/libmagic.dylib"
fi

if [[ -z "${TYPECODE_LIBMAGIC_DB_PATH:-}" && -f "/opt/homebrew/opt/libmagic/share/misc/magic.mgc" ]]; then
  export TYPECODE_LIBMAGIC_DB_PATH="/opt/homebrew/opt/libmagic/share/misc/magic.mgc"
fi

if [[ -n "${SCANCODE_BIN:-}" ]]; then
  if [[ -x "${SCANCODE_BIN}" ]]; then
    exec "${SCANCODE_BIN}" "$@"
  fi

  echo "SCANCODE_BIN is set but not executable: ${SCANCODE_BIN}" >&2
  exit 127
fi

if command -v scancode >/dev/null 2>&1; then
  exec "$(command -v scancode)" "$@"
fi

for candidate in \
  "./scancode" \
  "$HOME/.local/bin/scancode" \
  "$HOME"/Library/Python/*/bin/scancode \
  "$HOME/scancode-toolkit/scancode" \
  "/usr/local/bin/scancode" \
  "/opt/homebrew/bin/scancode"
do
  if [[ -x "$candidate" ]]; then
    exec "$candidate" "$@"
  fi
done

echo "ScanCode executable not found." >&2
echo "Install it and ensure scancode is on PATH, or set SCANCODE_BIN to the executable path." >&2
exit 127