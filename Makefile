.PHONY: build test test-extension e2e regression memory lint xpi install-host clean
build:
	cd host && cargo build --release --locked

test: build test-extension
	dbus-run-session -- python3 -m unittest discover -s tests -v

test-extension:
	npm test

e2e: build
	dbus-run-session -- python3 tests/e2e/run.py

regression: build
	dbus-run-session -- python3 tests/e2e/regression.py

memory:
	python3 tests/e2e/memory.py base && python3 tests/e2e/memory.py ext

lint:
	npm run lint

xpi:
	python3 scripts/package-extension.py

install-host:
	scripts/install-host.sh

clean:
	rm -rf dist host/target
