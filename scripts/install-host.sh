#!/usr/bin/env bash
# Installs the helper for the current user and registers it with Firefox-family browsers.
#   install-host.sh          build the helper and copy it to ~/.local/lib/mpris-bridge (survives moving this checkout)
#   install-host.sh --dev    build it and point the browser at this checkout's binary instead
#   install-host.sh --remove undo either
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
lib="$HOME/.local/lib/mpris-bridge"
name="mpris_bridge"
ext_id="mpris-bridge@totti786.github.io"

# Where each Firefox-family browser looks for native-messaging manifests; only those that exist are used
targets=("$HOME/.mozilla/native-messaging-hosts")
for dir in .librewolf .zen .floorp .waterfox; do
  [ -d "$HOME/$dir" ] && targets+=("$HOME/$dir/native-messaging-hosts")
done

if [ "${1:-}" = "--remove" ]; then
  for t in "${targets[@]}"; do rm -f "$t/$name.json"; done
  rm -rf "$lib"
  echo "removed"
  exit 0
fi

command -v cargo >/dev/null || { echo "cargo (Rust) is required to build the helper; install rust, or use a packaged release" >&2; exit 1; }
(cd "$here/host" && cargo build --release --locked)
bin="$here/host/target/release/mpris-bridge-host"

if [ "${1:-}" = "--dev" ]; then
  host="$bin"
else
  mkdir -p "$lib"
  install -m 755 "$bin" "$lib/mpris-bridge-host"
  host="$lib/mpris-bridge-host"
fi

for t in "${targets[@]}"; do
  mkdir -p "$t"
  cat > "$t/$name.json" <<JSON
{
  "name": "$name",
  "description": "MPRIS Bridge helper: publishes browser media tabs as MPRIS players",
  "path": "$host",
  "type": "stdio",
  "allowed_extensions": ["$ext_id"]
}
JSON
  echo "registered: $t/$name.json"
done
echo "helper: $host"
