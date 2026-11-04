#!/usr/bin/env bash
# Install this fork's helper under its own native-messaging name.
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
lib="$HOME/.local/lib/mpris-tab-bridge"
name="mpris_tab_bridge"
ext_id="mpris-tab-bridge@frixlt.github.io"
targets=("$HOME/.mozilla/native-messaging-hosts")
for dir in .librewolf .zen .floorp .waterfox .config/zen; do
  [ ! -d "$HOME/$dir" ] || targets+=("$HOME/$dir/native-messaging-hosts")
done
case "${1:-}" in
  --remove)
    for t in "${targets[@]}"; do rm -f "$t/$name.json"; done
    rm -f "$lib/mpris-bridge-host"
    rmdir "$lib" 2>/dev/null || true
    echo "removed MPRIS Tab Bridge helper registrations"; exit 0 ;;
  --binary)
    [ "$#" -eq 2 ] && [ -x "$2" ] || { echo "usage: $0 --binary /path/to/mpris-bridge-host" >&2; exit 1; }
    bin="$(readlink -f "$2")" ;;
  --dev|"")
    command -v cargo >/dev/null || { echo "Rust/cargo is required, or use --binary /path/to/helper" >&2; exit 1; }
    (cd "$here/host" && cargo build --release --locked)
    bin="$here/host/target/release/mpris-bridge-host" ;;
  *) echo "usage: $0 [--dev | --binary /path/to/helper | --remove]" >&2; exit 1 ;;
esac
command -v python3 >/dev/null || { echo "python3 is required to register the helper" >&2; exit 1; }
if [ "${1:-}" = --dev ]; then
  host="$bin"
else
  mkdir -p "$lib"
  host="$lib/mpris-bridge-host"
  [ "$bin" = "$host" ] || install -m 755 "$bin" "$host"
fi
for t in "${targets[@]}"; do
  mkdir -p "$t"
  python3 - "$t/$name.json" "$host" "$name" "$ext_id" <<'PY'
import json,sys
with open(sys.argv[1], 'w') as f:
    json.dump({'name':sys.argv[3], 'description':'MPRIS Tab Bridge local helper',
               'path':sys.argv[2], 'type':'stdio', 'allowed_extensions':[sys.argv[4]]},f,indent=2)
    f.write('\n')
PY
  echo "registered: $t/$name.json"
done
echo "helper: $host"
