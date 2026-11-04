# Firefox Add-ons submission draft

Name: **MPRIS Tab Bridge**

Summary: Independent Linux media controls for each Firefox tab, with artwork and per-tab volume. Requires a local helper.

## Description

Control browser media from your Linux desktop. Each tab with audio or video appears as a separate MPRIS player, so media panels and playerctl can control the right tab.

Features include playback, seeking, per-tab volume, artwork, next/previous when supported by the page, current YouTube video metadata and removal of players when tabs close or are discarded. Two tabs remain separate even when their titles match.

**Requires Linux, a session D-Bus and the separately installed native helper.** Installation and source: https://github.com/Frixlt/mpris-bridge

This is an independent MIT-licensed fork of totti786/mpris-bridge, with fixes for stale YouTube metadata and tab lifecycle. It is not affiliated with Mozilla, YouTube or the original project's maintainer.

Private windows, Chromium, Windows, macOS and Android are not supported. One player represents a tab, not each individual media element. Other browser media integrations may export additional browser-wide players; configure your desktop accordingly.

## Permissions and privacy

Reads media state and metadata on non-private web pages and sends it to a helper on the same computer. No analytics or remote backend. Other local applications can read MPRIS metadata through the session D-Bus. The browser downloads YouTube/Twitch artwork without cookies or referrers and passes it to the local helper, which temporarily caches images for desktop display. Other artwork may be downloaded by desktop widgets. See `PRIVACY.md`.

## Suggested listing fields

- Category: Other (media/desktop integration)
- Platforms: Linux desktop
- License: MIT
- Homepage and support: https://github.com/Frixlt/mpris-bridge
- Privacy policy: https://github.com/Frixlt/mpris-bridge/blob/main/PRIVACY.md
- Mark the first public build experimental while broader site compatibility is being evaluated.

## Reviewer notes

The extension needs the native host `mpris_tab_bridge`, authorized for add-on ID `mpris-tab-bridge@frixlt.github.io`. Build the Rust helper with `cargo build --release --locked` under `host/`, then run `scripts/install-host.sh`. Explicit image-CDN permissions allow YouTube thumbnails and Twitch avatars to be downloaded with credentials omitted. The helper validates image signatures and limits decoded images to 2 MiB before publishing local file URLs. There is no remote code, bundled minified code or build transformation required for extension JavaScript. All extension source is included in the XPI.

For a reproducible test: play media in two tabs, list players with `playerctl -l`, adjust one player's volume, navigate to a new YouTube video inside the same tab and close or discard a tab. `tests/e2e/regression.py` covers these lifecycle cases using local fixture pages. If the helper is absent, the background retries native messaging; it does not send metadata to a server.

The use of Firefox `wrappedJSObject`/`exportFunction` is limited to reading current YouTube player details and retaining page MediaSession action handlers for local media controls. No privileged extension API is exposed to page scripts.
