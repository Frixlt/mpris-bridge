# Fork release 1.1.5 — 2026-11-04

- Replace the Twitch-specific volume selector with a shared semantic HTML range-control resolver.
- Recognize volume controls by accessibility labels, associated labels and their surrounding component attributes, including Spotify's wrapper-labelled control.
- Reject disabled/invalid sliders and do not confuse unlabelled seek or layout-resize sliders with volume.
- Preserve 5% commands when a site's range input has a coarser keyboard step.
- Test the same implementation with a Twitch-style input, Spotify-style wrapper and a completely unknown website, including independent player routing and mute/unmute retention.

This is a common control path for detectable HTML sliders, not a promise of universal synchronization with every custom web-player UI. Media Session does not define a universal volume API.

# Fork release 1.1.4 — 2026-11-04

- Write volume through Twitch's own slider and input/change events so its saved volume, mute state, actual audio and desktop control stay synchronized.
- Use YouTube's setVolume/unMute/mute API when available rather than bypassing its player state.
- Read the site's effective volume and keep 0% while muted; positive panel adjustments restore sound at the requested level.
- Keep legitimate looping media registered while muted.
- Cover panel-to-site changes, site-to-panel changes, mute/unmute volume retention and muted looping media in browser regression tests.

# Fork release 1.1.3 — 2026-11-04

- Copy YouTube thumbnail primitives into the content-script compartment before filtering/sorting, so Firefox's cross-compartment restrictions do not prevent player reports.
- Ignore inaccessible thumbnail entries without losing the current video's title/identity.
- Exercise actual page-owned thumbnail arrays in the browser regression fixture.

# Fork release 1.1.2 — 2026-11-04

- Bind live Twitch channel avatars to channel-labelled/linked images in the current DOM, ignoring stale OpenGraph/MediaSession artwork after SPA navigation.
- Show no avatar during a transition until an image for the requested channel exists; never relabel the previous channel's avatar.
- Use native wide YouTube thumbnails when available and a 16:9 fallback to avoid letterbox bars in circular covers.
- Add a real-browser regression for switching Twitch channels while og:image remains stale.

# Fork release 1.1.1 — 2026-11-04

- Download YouTube thumbnails and Twitch channel avatars in the browser, without cookies/referrers, and pass validated image bytes to the native helper.
- Publish local artwork files through MPRIS so panels do not need independent access to image CDNs.
- Keep cached artwork across ordinary metadata heartbeats; reject downloads completing after the active artwork changed.
- Remove temporary artwork files with their tab and reject invalid or oversized image payloads.
- Preserve Twitch channel avatars; do not substitute an earlier channel's stream preview.
- Add explicit image-CDN permissions and document image requests and temporary cache storage in the privacy policy.

Version 1.1.1 requires updating the extension and native helper. The `artData` protocol field is optional; older metadata-only messages remain supported. This update has not been submitted to Mozilla automatically.

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
