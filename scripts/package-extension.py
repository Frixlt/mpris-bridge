#!/usr/bin/env python3
"""Produce a deterministic unsigned XPI from the extension source, plus SHA-256."""

import hashlib, json, pathlib, zipfile

root = pathlib.Path(__file__).resolve().parents[1]
version = json.loads((root / "extension/manifest.json").read_text())["version"]
out = root / "dist" / f"mpris-tab-bridge-{version}-unsigned.xpi"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for source in sorted((root / "extension").rglob("*")):
        if not source.is_file():
            continue
        entry = zipfile.ZipInfo(
            source.relative_to(root / "extension").as_posix(),
            date_time=(2026, 1, 1, 0, 0, 0),
        )
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, source.read_bytes())
checksum = f"{hashlib.sha256(out.read_bytes()).hexdigest()}  {out.name}\n"
out.with_suffix(out.suffix + ".sha256").write_text(checksum)
print(out)
print(checksum, end="")
