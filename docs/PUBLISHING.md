# Publishing MPRIS Tab Bridge

This fork is maintained at https://github.com/Frixlt/mpris-bridge and must be submitted as a **new** add-on, not an update to totti786's MPRIS Bridge listing.

## Stable identity

- Name: MPRIS Tab Bridge
- Add-on ID: `mpris-tab-bridge@frixlt.github.io`
- Native host: `mpris_tab_bridge`
- License: MIT, including the upstream copyright notice
- Desktop Linux only; a separately installed native helper is required

Keep the add-on ID and `allowed_extensions` in both helper installers identical. Do not reuse the upstream add-on ID. Once signed, the ID identifies future updates and should remain unchanged.

## Verify and package

Run `npm ci --ignore-scripts`, `npm test`, `npm run lint`, `make test`, `make e2e` and the browser regression suite documented in the README. Check that two tabs have independent volume and that closed/discarded tabs disappear. Update the extension, npm, helper and packaging versions and the changelog together.

`make xpi` creates `dist/mpris-tab-bridge-<version>-unsigned.xpi` and its SHA-256 file. Packaging includes only `extension/`, without tests, logs, native binaries, credentials or minification. Repeating the command for unchanged source produces the same hash.

GitHub Actions uploads the unsigned extension as a workflow artifact. It is a review package, not a permanent Firefox installer. Do not label it as signed.

## Submit to Firefox Add-ons

Follow Mozilla's [submission guide](https://extensionworkshop.com/documentation/publish/submitting-an-add-on/) and [signing overview](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).

1. Sign in with the maintainer's Mozilla account and open the Add-ons Developer Hub.
2. Choose Submit a New Add-on and **On this site** for a public listing.
3. Upload the unsigned XPI. Resolve validation issues, select Linux desktop compatibility and provide the listing from `docs/AMO-LISTING.md`.
4. Supply the privacy policy and reviewer notes. State clearly that a local native helper is required and link to the helper source and installation instructions.
5. The maintainer reviews and accepts Mozilla's current developer agreement and submits the release. The repository does not store signing credentials.
6. Wait for Mozilla signing/review. Only after approval, publish the actual Add-ons listing URL in the README and distribute the signed XPI.

For command-line signing, `web-ext sign` supports listed and unlisted distribution. Keep API credentials in the local environment or GitHub Actions secrets; never commit them or paste them into issue bodies. Do not add an `update_url` for AMO-listed releases; AMO supplies updates.

## GitHub release

Create a release tag such as `v1.1.0` from the verified main commit. Attach the unsigned XPI with an explicit label, SHA-256 file and a helper built from the tagged source. When available, attach Mozilla's signed XPI separately. Preserve the tag and original commit as the source of each artifact.

GitHub publication does not provide Mozilla signing or store approval. Avoid publishing screenshots or logs containing personal tab titles, browser profiles, tokens or account data.
