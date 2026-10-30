VERSION := $(shell python3 -c "import json;print(json.load(open('extension/manifest.json'))['version'])")

.PHONY: build test e2e memory lint xpi install-host clean

build:
	cd host && cargo build --release --locked

test: build
	dbus-run-session -- python3 -m unittest discover -s tests -v

# Real headless Firefox with a throwaway profile; needs firefox, npx, ffmpeg and a session bus
e2e: build
	dbus-run-session -- python3 tests/e2e/run.py

# Control vs extension, 12 tabs; see docs/MEMORY.md
memory:
	python3 tests/e2e/memory.py base && python3 tests/e2e/memory.py ext

lint:
	cd extension && npx --yes web-ext lint

# An unsigned package, for review uploads or signing; Firefox release only installs it once Mozilla has signed it
xpi:
	mkdir -p dist
	cd extension && zip -r -FS ../dist/mpris-bridge-$(VERSION).xpi . -x '*.svg'

install-host:
	scripts/install-host.sh

clean:
	rm -rf dist host/target
