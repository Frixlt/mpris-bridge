# Fork release 1.1.0 — 2026-11-04

- Publish as MPRIS Tab Bridge with an independent add-on ID and native host registration.
- Track live document ports instead of keeping reports after a document disappears.
- Handle discarded tabs and removed frames; request fresh state after helper reconnect.
- Reject stale top-frame reports after URL changes.
- Resolve YouTube title/artist/artwork using current video details and verify the requested video ID.
- Add extension lifecycle/routing tests and a browser regression suite covering SPA navigation, per-tab volume, closing and discarding.
- Add deterministic unsigned packaging and store submission documentation.

The native JSON protocol and MPRIS bus-name prefix remain compatible with upstream.
This source release has not yet been signed or published on Firefox Add-ons.

---

# Changelog

## 1.0.0

First release. Every Firefox tab with media becomes its own MPRIS player, with title, artist, album and cover art from the page, seeking, volume, speed, next and previous where the page offers them, and a paused state while a stream is buffering. The helper is a small Rust binary; the extension is plain JavaScript.
