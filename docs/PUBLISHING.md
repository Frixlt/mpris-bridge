# Releasing

Firefox only installs extensions that Mozilla has signed, and no browser store can ship the helper, so a release has three parts.

## 1. Tag

Bump `version` in `extension/manifest.json`, `host/Cargo.toml` and `packaging/PKGBUILD`, add an entry to `CHANGELOG.md`, run `make test e2e lint`, then:

```
git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin main vX.Y.Z
```

Attach `dist/mpris-bridge-X.Y.Z.xpi` (from `make xpi`) and a release build of the helper to the GitHub release.

## 2. Extension (addons.mozilla.org)

Create API keys under Developer Hub, Manage API Keys. Then either upload the `.xpi` by hand at "Submit a New Add-on", or sign it from the command line:

```
cd extension
npx web-ext sign --channel=listed --api-key=... --api-secret=...
```

Use `--channel=unlisted` to get a signed file you host yourself. The source isn't minified, so reviewers need no separate upload. In the listing, say plainly that the add-on needs the helper from the README and that nothing leaves the machine. Reviewers will run it without the helper, in which case it just keeps quietly retrying to connect.

The add-on id, `mpris-bridge@totti786.github.io`, can't change once Mozilla has signed it. It has to match `allowed_extensions` in `scripts/install-host.sh` and `packaging/PKGBUILD`.

## 3. AUR

```
git clone ssh://aur@aur.archlinux.org/mpris-bridge.git aur-mpris-bridge
cp packaging/PKGBUILD aur-mpris-bridge/ && cd aur-mpris-bridge
updpkgsums && makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO && git commit -m "Update to X.Y.Z" && git push
```

## Keep in step

The helper and the extension talk through the JSON messages described at the top of `host/src/main.rs`. A change that older helpers or extensions can't read needs a new native host name, or a version field in the messages.
