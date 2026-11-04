# MPRIS Tab Bridge

Independent Linux media controls for each Firefox or Zen tab. Each tab with media gets its own MPRIS player, artwork, playback controls and volume. Desktop panels, media keys and `playerctl` can address each player separately.

This is a fork of [totti786/mpris-bridge](https://github.com/totti786/mpris-bridge), distributed under the original MIT license. The fork fixes stale YouTube metadata and players left behind by navigated, closed or discarded tabs. It has its own add-on ID and native-messaging registration.

## Status

Version **1.1.2** is a development release. Version 1.1.0 was submitted for Mozilla review; versions 1.1.1–1.1.2 add local artwork delivery and needs a separate signed update. GitHub's unsigned XPI is suitable for temporary installation and submission to Mozilla; it does not bypass Firefox signing requirements.

## Install the local helper

On Linux, with Rust/cargo, Python 3 and a D-Bus session available:

```sh
git clone https://github.com/Frixlt/mpris-bridge.git
cd mpris-bridge
scripts/install-host.sh
```

The installer copies the helper to `~/.local/lib/mpris-tab-bridge/` and registers the native host `mpris_tab_bridge` for Firefox and detected Firefox-family browsers, including Zen's `.config/zen` location. It preserves the original MPRIS Bridge installation. It does not install or modify desktop panels.

To register an already built helper instead of building Rust:

```sh
scripts/install-host.sh --binary /absolute/path/to/mpris-bridge-host
```

To remove this fork's helper and registrations: `scripts/install-host.sh --remove`.

## Load the extension for testing

1. Disable the original **MPRIS Bridge** extension in `about:addons` to avoid two independent extensions exporting the same tabs.
2. Open `about:debugging#/runtime/this-firefox`.
3. Select **Load Temporary Add-on** and choose `extension/manifest.json`.
4. Reload existing media tabs. Content scripts are injected into newly loaded documents.

Temporary installations last until browser restart. A permanent Firefox installation requires a Mozilla-signed build; see [publishing](docs/PUBLISHING.md).

Open two media tabs and run:

```sh
playerctl -l
playerctl --player='firefox_bridge.p1234t1' volume 0.30
```

Replace the example name with an actual player from the list. Only that tab's media element changes volume. The bridge never changes global system volume.

## Changes in this fork

- Live content-script ports own frame state. Closing a tab, removing an iframe or discarding a Zen tab removes its state without a timeout-based supervisor.
- Restarting the native helper requests fresh reports from live documents instead of replaying cached metadata.
- YouTube metadata comes from the current player video details. The video ID must agree with the requested watch/shorts/embed/live URL; an old title and cover are not relabelled with a new URL during navigation.
- Album artwork on YouTube uses the verified current video ID. Other sites continue to use MediaSession metadata, page title and `og:image`.
- Twitch avatars are selected from a page image labelled or linked to the current channel, so stale MediaSession/OpenGraph metadata cannot retain a previous channel after navigation.
- YouTube thumbnails and Twitch avatars are downloaded by the browser and passed to the native helper as validated image bytes. MPRIS advertises a local image file, avoiding a second download by desktop panels. Twitch keeps channel avatars rather than live-frame thumbnails.
- Every tab remains independent, even if two tabs have the same title or URL. Embedded frames are selected within their owning tab, with a playing frame preferred.

YouTube uses an internal page API for video details. Site changes may require a follow-up fix. The bridge exports one player per tab, not one per media element within a tab.

## Browser-global duplicates

Firefox's built-in media integration and Plasma Browser Integration may independently export a browser-wide player. This extension cannot remove another program's D-Bus service. Configure your panel to prefer per-tab players or disable the competing media integration if desired. Two instances of this fork must not be merged by application name, title or URL.

The D-Bus prefix `org.mpris.MediaPlayer2.firefox_bridge.*` is retained for desktop compatibility. The add-on ID is `mpris-tab-bridge@frixlt.github.io`; the native host is `mpris_tab_bridge`. Original MPRIS Bridge native manifests do not authorize this new ID.

## Privacy and permissions

See [PRIVACY.md](PRIVACY.md). The extension reads media in non-private tabs and sends titles, URLs, artwork URLs and playback state to the local helper. Other applications in the same desktop session can read that metadata from D-Bus. Private tabs are ignored. There are no analytics, remote executable scripts or external accounts. The extension downloads YouTube/Twitch artwork without cookies or page referrers and passes it to the helper for temporary local caching; panels may download artwork from other providers.

Linux Firefox-family browsers are supported. Chromium, Windows, macOS and Android are not supported. Flatpak/sandboxed browsers need separate native-messaging integration and are not covered by this installer.

## Build and verify

```sh
npm ci --ignore-scripts
npm test                     # extension routing and lifecycle regression tests
npm run lint                 # Mozilla web-ext validation
make test                    # Rust helper build and real D-Bus tests
make e2e                     # original browser/media control smoke test
make xpi                     # deterministic unsigned XPI + SHA-256 in dist/
```

For the browser regression suite, install Firefox or Zen, geckodriver, ffmpeg, Python PyGObject and Selenium. Use a virtual environment with `--system-site-packages` if PyGObject comes from the distribution:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-test.txt
FIREFOX=/opt/zen-browser-bin/zen-bin dbus-run-session -- .venv/bin/python tests/e2e/regression.py
```

`FIREFOX` must point to the real Firefox/Zen executable, not a shell launcher. `FIREFOX`, `GECKODRIVER` and `MPRIS_BRIDGE_HOST` can select the browser, driver and helper. The regression suite uses a throwaway profile, its own local fixture server and a private D-Bus session. It tests stale MediaSession data, SPA transitions, independent tab volume, navigation, tab close and actual browser tab discard.

## License and attribution

MIT. Original project copyright © 2026 totti786; fork changes © 2026 Frixlt. The original copyright notice is preserved in [LICENSE](LICENSE). Historical memory measurements in `docs/MEMORY.md` describe the upstream version, not a fresh benchmark of this fork.
